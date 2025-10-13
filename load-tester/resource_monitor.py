"""
Resource Protection and Monitoring System for Load Testing Automation
"""
import asyncio
import logging
import psutil
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import threading

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """Types of system resources to monitor"""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"
    CONNECTIONS = "connections"

class ResourceStatus(Enum):
    """Status of resource usage"""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class LoadAdjustmentAction(Enum):
    """Actions to take for load adjustment"""
    NONE = "none"
    REDUCE_WORKERS = "reduce_workers"
    THROTTLE_REQUESTS = "throttle_requests"
    PAUSE_TEST = "pause_test"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class ResourceThresholds:
    """Thresholds for resource monitoring"""
    cpu_warning: float = 70.0      # CPU usage percentage
    cpu_critical: float = 85.0
    cpu_emergency: float = 95.0
    
    memory_warning: float = 70.0   # Memory usage percentage
    memory_critical: float = 85.0
    memory_emergency: float = 95.0
    
    network_warning: float = 80.0  # Network usage percentage (if available)
    network_critical: float = 90.0
    network_emergency: float = 95.0
    
    disk_warning: float = 80.0     # Disk usage percentage
    disk_critical: float = 90.0
    disk_emergency: float = 95.0
    
    connections_warning: int = 1000  # Number of connections
    connections_critical: int = 2000
    connections_emergency: int = 5000
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert thresholds to dictionary"""
        return {
            "cpu": {
                "warning": self.cpu_warning,
                "critical": self.cpu_critical,
                "emergency": self.cpu_emergency
            },
            "memory": {
                "warning": self.memory_warning,
                "critical": self.memory_critical,
                "emergency": self.memory_emergency
            },
            "network": {
                "warning": self.network_warning,
                "critical": self.network_critical,
                "emergency": self.network_emergency
            },
            "disk": {
                "warning": self.disk_warning,
                "critical": self.disk_critical,
                "emergency": self.disk_emergency
            },
            "connections": {
                "warning": self.connections_warning,
                "critical": self.connections_critical,
                "emergency": self.connections_emergency
            }
        }

@dataclass
class ResourceUsage:
    """Current resource usage information"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_mb: float
    disk_percent: float
    network_connections: int
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0
    load_average: Optional[List[float]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert resource usage to dictionary"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "memory_available_mb": self.memory_available_mb,
            "disk_percent": self.disk_percent,
            "network_connections": self.network_connections,
            "network_bytes_sent": self.network_bytes_sent,
            "network_bytes_recv": self.network_bytes_recv,
            "load_average": self.load_average
        }

@dataclass
class ResourceAlert:
    """Alert for resource threshold violation"""
    resource_type: ResourceType
    status: ResourceStatus
    current_value: float
    threshold_value: float
    message: str
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert alert to dictionary"""
        return {
            "resource_type": self.resource_type.value,
            "status": self.status.value,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }

class ResourceMonitor:
    """
    System resource monitor with automatic load adjustment
    """
    
    def __init__(self, 
                 thresholds: Optional[ResourceThresholds] = None,
                 monitoring_interval: float = 5.0):
        self.thresholds = thresholds or ResourceThresholds()
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        # Resource usage history
        self.usage_history: List[ResourceUsage] = []
        self.max_history_size = 720  # 1 hour at 5-second intervals
        
        # Alert system
        self.active_alerts: Dict[ResourceType, ResourceAlert] = {}
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []
        
        # Load adjustment
        self.load_adjustment_callbacks: List[Callable[[LoadAdjustmentAction, Dict[str, Any]], None]] = []
        self.last_adjustment_time: Optional[datetime] = None
        self.adjustment_cooldown = 30.0  # seconds
        
        # Connection limits
        self.max_connections = 1000
        self.current_connections = 0
        self.connection_lock = threading.Lock()
        
        # Network baseline (for calculating usage percentage)
        self._network_baseline: Optional[Dict[str, int]] = None
        self._last_network_stats: Optional[Dict[str, int]] = None
    
    async def start_monitoring(self):
        """Start resource monitoring"""
        try:
            if self.is_monitoring:
                logger.warning("Resource monitoring is already running")
                return
            
            self.is_monitoring = True
            self._stop_event.clear()
            
            # Initialize network baseline
            await self._initialize_network_baseline()
            
            # Start monitoring task
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            
            logger.info("Resource monitoring started")
            
        except Exception as e:
            self.is_monitoring = False
            logger.error(f"Error starting resource monitoring: {e}")
            raise
    
    async def stop_monitoring(self):
        """Stop resource monitoring"""
        try:
            if not self.is_monitoring:
                return
            
            self.is_monitoring = False
            self._stop_event.set()
            
            # Cancel monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Resource monitoring stopped")
            
        except Exception as e:
            logger.error(f"Error stopping resource monitoring: {e}")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while not self._stop_event.is_set():
                try:
                    # Collect resource usage
                    usage = await self._collect_resource_usage()
                    
                    # Store in history
                    self.usage_history.append(usage)
                    if len(self.usage_history) > self.max_history_size:
                        self.usage_history.pop(0)
                    
                    # Check thresholds and generate alerts
                    await self._check_thresholds(usage)
                    
                    # Wait for next monitoring cycle
                    try:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=self.monitoring_interval
                        )
                        break  # Stop requested
                    except asyncio.TimeoutError:
                        continue  # Normal monitoring cycle
                        
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(1.0)
                    
        except asyncio.CancelledError:
            logger.info("Resource monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
    
    async def _collect_resource_usage(self) -> ResourceUsage:
        """Collect current resource usage"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available_mb = memory.available / (1024 * 1024)
            
            # Disk usage (root partition)
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network connections
            connections = psutil.net_connections()
            network_connections = len(connections)
            
            # Network I/O
            net_io = psutil.net_io_counters()
            network_bytes_sent = net_io.bytes_sent
            network_bytes_recv = net_io.bytes_recv
            
            # Load average (Unix-like systems)
            load_average = None
            try:
                load_average = list(psutil.getloadavg())
            except (AttributeError, OSError):
                # Not available on all systems
                pass
            
            return ResourceUsage(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                memory_available_mb=memory_available_mb,
                disk_percent=disk_percent,
                network_connections=network_connections,
                network_bytes_sent=network_bytes_sent,
                network_bytes_recv=network_bytes_recv,
                load_average=load_average
            )
            
        except Exception as e:
            logger.error(f"Error collecting resource usage: {e}")
            # Return default values on error
            return ResourceUsage(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_available_mb=0.0,
                disk_percent=0.0,
                network_connections=0
            )
    
    async def _initialize_network_baseline(self):
        """Initialize network baseline for usage calculation"""
        try:
            net_io = psutil.net_io_counters()
            self._network_baseline = {
                'bytes_sent': net_io.bytes_sent,
                'bytes_recv': net_io.bytes_recv
            }
            self._last_network_stats = self._network_baseline.copy()
            
        except Exception as e:
            logger.error(f"Error initializing network baseline: {e}")
    
    async def _check_thresholds(self, usage: ResourceUsage):
        """Check resource usage against thresholds and generate alerts"""
        try:
            # Check CPU
            await self._check_resource_threshold(
                ResourceType.CPU,
                usage.cpu_percent,
                self.thresholds.cpu_warning,
                self.thresholds.cpu_critical,
                self.thresholds.cpu_emergency,
                f"CPU usage: {usage.cpu_percent:.1f}%"
            )
            
            # Check Memory
            await self._check_resource_threshold(
                ResourceType.MEMORY,
                usage.memory_percent,
                self.thresholds.memory_warning,
                self.thresholds.memory_critical,
                self.thresholds.memory_emergency,
                f"Memory usage: {usage.memory_percent:.1f}% ({usage.memory_available_mb:.0f}MB available)"
            )
            
            # Check Disk
            await self._check_resource_threshold(
                ResourceType.DISK,
                usage.disk_percent,
                self.thresholds.disk_warning,
                self.thresholds.disk_critical,
                self.thresholds.disk_emergency,
                f"Disk usage: {usage.disk_percent:.1f}%"
            )
            
            # Check Connections
            await self._check_resource_threshold(
                ResourceType.CONNECTIONS,
                usage.network_connections,
                self.thresholds.connections_warning,
                self.thresholds.connections_critical,
                self.thresholds.connections_emergency,
                f"Network connections: {usage.network_connections}"
            )
            
        except Exception as e:
            logger.error(f"Error checking thresholds: {e}")
    
    async def _check_resource_threshold(self,
                                      resource_type: ResourceType,
                                      current_value: float,
                                      warning_threshold: float,
                                      critical_threshold: float,
                                      emergency_threshold: float,
                                      message: str):
        """Check individual resource threshold"""
        try:
            # Determine status
            if current_value >= emergency_threshold:
                status = ResourceStatus.EMERGENCY
                threshold = emergency_threshold
            elif current_value >= critical_threshold:
                status = ResourceStatus.CRITICAL
                threshold = critical_threshold
            elif current_value >= warning_threshold:
                status = ResourceStatus.WARNING
                threshold = warning_threshold
            else:
                status = ResourceStatus.NORMAL
                threshold = warning_threshold
            
            # Check if status changed
            previous_alert = self.active_alerts.get(resource_type)
            
            if status == ResourceStatus.NORMAL:
                # Clear alert if it exists
                if previous_alert:
                    del self.active_alerts[resource_type]
                    logger.info(f"Resource alert cleared: {resource_type.value}")
            else:
                # Create or update alert
                alert = ResourceAlert(
                    resource_type=resource_type,
                    status=status,
                    current_value=current_value,
                    threshold_value=threshold,
                    message=message,
                    timestamp=datetime.now()
                )
                
                # Only trigger if status worsened or it's a new alert
                if (not previous_alert or 
                    previous_alert.status.value != status.value):
                    
                    self.active_alerts[resource_type] = alert
                    await self._trigger_alert(alert)
            
        except Exception as e:
            logger.error(f"Error checking resource threshold: {e}")
    
    async def _trigger_alert(self, alert: ResourceAlert):
        """Trigger alert and determine load adjustment action"""
        try:
            logger.warning(f"Resource alert: {alert.message}")
            
            # Notify alert callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    logger.error(f"Error in alert callback: {e}")
            
            # Determine load adjustment action
            action = self._determine_load_adjustment(alert)
            
            if action != LoadAdjustmentAction.NONE:
                await self._execute_load_adjustment(action, alert)
                
        except Exception as e:
            logger.error(f"Error triggering alert: {e}")
    
    def _determine_load_adjustment(self, alert: ResourceAlert) -> LoadAdjustmentAction:
        """Determine what load adjustment action to take"""
        try:
            # Check cooldown period
            if (self.last_adjustment_time and 
                (datetime.now() - self.last_adjustment_time).total_seconds() < self.adjustment_cooldown):
                return LoadAdjustmentAction.NONE
            
            # Determine action based on status and resource type
            if alert.status == ResourceStatus.EMERGENCY:
                if alert.resource_type in [ResourceType.CPU, ResourceType.MEMORY]:
                    return LoadAdjustmentAction.EMERGENCY_STOP
                else:
                    return LoadAdjustmentAction.PAUSE_TEST
            
            elif alert.status == ResourceStatus.CRITICAL:
                if alert.resource_type == ResourceType.CONNECTIONS:
                    return LoadAdjustmentAction.REDUCE_WORKERS
                else:
                    return LoadAdjustmentAction.THROTTLE_REQUESTS
            
            elif alert.status == ResourceStatus.WARNING:
                return LoadAdjustmentAction.THROTTLE_REQUESTS
            
            return LoadAdjustmentAction.NONE
            
        except Exception as e:
            logger.error(f"Error determining load adjustment: {e}")
            return LoadAdjustmentAction.NONE
    
    async def _execute_load_adjustment(self, action: LoadAdjustmentAction, alert: ResourceAlert):
        """Execute load adjustment action"""
        try:
            self.last_adjustment_time = datetime.now()
            
            # Prepare adjustment context
            context = {
                "resource_type": alert.resource_type.value,
                "current_value": alert.current_value,
                "threshold_value": alert.threshold_value,
                "message": alert.message
            }
            
            logger.warning(f"Executing load adjustment: {action.value}")
            
            # Notify load adjustment callbacks
            for callback in self.load_adjustment_callbacks:
                try:
                    callback(action, context)
                except Exception as e:
                    logger.error(f"Error in load adjustment callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error executing load adjustment: {e}")
    
    def acquire_connection(self) -> bool:
        """
        Acquire a connection slot (for connection limiting)
        
        Returns:
            True if connection acquired, False if limit reached
        """
        try:
            with self.connection_lock:
                if self.current_connections >= self.max_connections:
                    return False
                
                self.current_connections += 1
                return True
                
        except Exception as e:
            logger.error(f"Error acquiring connection: {e}")
            return False
    
    def release_connection(self):
        """Release a connection slot"""
        try:
            with self.connection_lock:
                if self.current_connections > 0:
                    self.current_connections -= 1
                    
        except Exception as e:
            logger.error(f"Error releasing connection: {e}")
    
    def set_connection_limit(self, limit: int):
        """Set maximum connection limit"""
        try:
            with self.connection_lock:
                self.max_connections = max(1, limit)
                logger.info(f"Connection limit set to {self.max_connections}")
                
        except Exception as e:
            logger.error(f"Error setting connection limit: {e}")
    
    def get_current_usage(self) -> Optional[ResourceUsage]:
        """Get most recent resource usage"""
        if self.usage_history:
            return self.usage_history[-1]
        return None
    
    def get_usage_history(self, minutes: int = 10) -> List[ResourceUsage]:
        """Get resource usage history for specified minutes"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            return [
                usage for usage in self.usage_history
                if usage.timestamp >= cutoff_time
            ]
        except Exception as e:
            logger.error(f"Error getting usage history: {e}")
            return []
    
    def get_active_alerts(self) -> List[ResourceAlert]:
        """Get list of active alerts"""
        return list(self.active_alerts.values())
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get comprehensive resource status"""
        try:
            current_usage = self.get_current_usage()
            
            return {
                "monitoring_active": self.is_monitoring,
                "current_usage": current_usage.to_dict() if current_usage else None,
                "active_alerts": [alert.to_dict() for alert in self.active_alerts.values()],
                "thresholds": self.thresholds.to_dict(),
                "connection_info": {
                    "current_connections": self.current_connections,
                    "max_connections": self.max_connections,
                    "utilization_percent": (self.current_connections / self.max_connections * 100) if self.max_connections > 0 else 0
                },
                "last_adjustment_time": self.last_adjustment_time.isoformat() if self.last_adjustment_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting resource status: {e}")
            return {"error": str(e)}
    
    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Add callback for resource alerts"""
        self.alert_callbacks.append(callback)
    
    def add_load_adjustment_callback(self, callback: Callable[[LoadAdjustmentAction, Dict[str, Any]], None]):
        """Add callback for load adjustments"""
        self.load_adjustment_callbacks.append(callback)
    
    def remove_alert_callback(self, callback: Callable[[ResourceAlert], None]):
        """Remove alert callback"""
        if callback in self.alert_callbacks:
            self.alert_callbacks.remove(callback)
    
    def remove_load_adjustment_callback(self, callback: Callable[[LoadAdjustmentAction, Dict[str, Any]], None]):
        """Remove load adjustment callback"""
        if callback in self.load_adjustment_callbacks:
            self.load_adjustment_callbacks.remove(callback)
    
    def update_thresholds(self, new_thresholds: ResourceThresholds):
        """Update resource thresholds"""
        try:
            self.thresholds = new_thresholds
            logger.info("Resource thresholds updated")
        except Exception as e:
            logger.error(f"Error updating thresholds: {e}")
    
    def clear_alerts(self):
        """Clear all active alerts"""
        try:
            self.active_alerts.clear()
            logger.info("All resource alerts cleared")
        except Exception as e:
            logger.error(f"Error clearing alerts: {e}")

# Global resource monitor instance
resource_monitor = ResourceMonitor()