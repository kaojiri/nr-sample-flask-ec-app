"""
Statistics Collection and Real-time Monitoring for Load Testing
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from threading import Lock
import json
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class RequestMetric:
    """Individual request metric data point"""
    timestamp: datetime
    endpoint: str
    method: str
    status_code: Optional[int]
    response_time: float
    success: bool
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "timestamp": self.timestamp.isoformat(),
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "response_time": self.response_time,
            "success": self.success,
            "error_message": self.error_message
        }

@dataclass
class TimeWindowStats:
    """Statistics for a specific time window"""
    window_start: datetime
    window_end: datetime
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    error_count_by_code: Dict[int, int] = field(default_factory=dict)
    endpoint_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests
    
    @property
    def requests_per_second(self) -> float:
        """Calculate requests per second for this window"""
        duration = (self.window_end - self.window_start).total_seconds()
        if duration <= 0:
            return 0.0
        return self.total_requests / duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "min_response_time": self.min_response_time if self.min_response_time != float('inf') else 0.0,
            "max_response_time": self.max_response_time,
            "requests_per_second": self.requests_per_second,
            "error_count_by_code": self.error_count_by_code,
            "endpoint_stats": self.endpoint_stats
        }

@dataclass
class RealTimeStats:
    """Real-time aggregated statistics"""
    session_id: str
    start_time: datetime
    last_update: datetime
    
    # Overall statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0
    
    # Rate statistics
    current_rps: float = 0.0  # Current requests per second
    peak_rps: float = 0.0     # Peak requests per second
    
    # Error statistics
    error_count_by_code: Dict[int, int] = field(default_factory=dict)
    error_rate_last_minute: float = 0.0
    
    # Endpoint statistics
    endpoint_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Performance percentiles (approximated)
    response_time_p50: float = 0.0
    response_time_p95: float = 0.0
    response_time_p99: float = 0.0
    
    @property
    def success_rate(self) -> float:
        """Calculate overall success rate as percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate overall average response time"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests
    
    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds"""
        return (self.last_update - self.start_time).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update.isoformat(),
            "duration_seconds": self.duration_seconds,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": self.success_rate,
            "average_response_time": self.average_response_time,
            "min_response_time": self.min_response_time if self.min_response_time != float('inf') else 0.0,
            "max_response_time": self.max_response_time,
            "current_rps": self.current_rps,
            "peak_rps": self.peak_rps,
            "error_count_by_code": self.error_count_by_code,
            "error_rate_last_minute": self.error_rate_last_minute,
            "endpoint_stats": self.endpoint_stats,
            "response_time_p50": self.response_time_p50,
            "response_time_p95": self.response_time_p95,
            "response_time_p99": self.response_time_p99
        }

class StatisticsCollector:
    """
    Collects and aggregates statistics from load testing requests
    with real-time monitoring capabilities
    """
    
    def __init__(self, session_id: str, max_metrics_in_memory: int = 10000):
        self.session_id = session_id
        self.max_metrics_in_memory = max_metrics_in_memory
        
        # Thread-safe data structures
        self._lock = Lock()
        self._metrics: deque = deque(maxlen=max_metrics_in_memory)
        self._response_times: deque = deque(maxlen=1000)  # For percentile calculations
        
        # Real-time statistics
        self.stats = RealTimeStats(
            session_id=session_id,
            start_time=datetime.now(),
            last_update=datetime.now()
        )
        
        # Time window tracking
        self._time_windows: Dict[str, TimeWindowStats] = {}
        self._window_size_seconds = 60  # 1-minute windows
        
        # Callbacks for real-time updates
        self._update_callbacks: List[Callable[[RealTimeStats], None]] = []
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    def start_monitoring(self):
        """Start background monitoring and statistics calculation"""
        if self._is_running:
            return
        
        self._is_running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"Statistics monitoring started for session {self.session_id}")
    
    async def stop_monitoring(self):
        """Stop background monitoring"""
        self._is_running = False
        
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Statistics monitoring stopped for session {self.session_id}")
    
    def record_request(self, 
                      endpoint: str,
                      method: str,
                      status_code: Optional[int],
                      response_time: float,
                      success: bool,
                      error_message: Optional[str] = None):
        """
        Record a single request metric
        
        Args:
            endpoint: Request endpoint
            method: HTTP method
            status_code: HTTP status code (None if connection failed)
            response_time: Response time in seconds
            success: Whether request was successful
            error_message: Error message if request failed
        """
        try:
            metric = RequestMetric(
                timestamp=datetime.now(),
                endpoint=endpoint,
                method=method,
                status_code=status_code,
                response_time=response_time,
                success=success,
                error_message=error_message
            )
            
            with self._lock:
                self._metrics.append(metric)
                
                # Update response times for percentile calculation
                if success and response_time > 0:
                    self._response_times.append(response_time)
                
                # Update real-time statistics
                self._update_realtime_stats(metric)
                
                # Update time window statistics
                self._update_time_window_stats(metric)
            
            # Notify callbacks
            self._notify_callbacks()
            
        except Exception as e:
            logger.error(f"Error recording request metric: {e}")
    
    def _update_realtime_stats(self, metric: RequestMetric):
        """Update real-time statistics with new metric (called with lock held)"""
        try:
            self.stats.last_update = metric.timestamp
            self.stats.total_requests += 1
            
            if metric.success:
                self.stats.successful_requests += 1
                self.stats.total_response_time += metric.response_time
                
                # Update min/max response times
                if metric.response_time < self.stats.min_response_time:
                    self.stats.min_response_time = metric.response_time
                if metric.response_time > self.stats.max_response_time:
                    self.stats.max_response_time = metric.response_time
            else:
                self.stats.failed_requests += 1
                
                # Track error codes
                if metric.status_code:
                    self.stats.error_count_by_code[metric.status_code] = \
                        self.stats.error_count_by_code.get(metric.status_code, 0) + 1
            
            # Update endpoint statistics
            self._update_endpoint_stats(metric)
            
        except Exception as e:
            logger.error(f"Error updating real-time stats: {e}")
    
    def _update_endpoint_stats(self, metric: RequestMetric):
        """Update per-endpoint statistics (called with lock held)"""
        try:
            endpoint = metric.endpoint
            
            if endpoint not in self.stats.endpoint_stats:
                self.stats.endpoint_stats[endpoint] = {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "total_response_time": 0.0,
                    "min_response_time": float('inf'),
                    "max_response_time": 0.0,
                    "last_request_time": None
                }
            
            ep_stats = self.stats.endpoint_stats[endpoint]
            ep_stats["total_requests"] += 1
            ep_stats["last_request_time"] = metric.timestamp.isoformat()
            
            if metric.success:
                ep_stats["successful_requests"] += 1
                ep_stats["total_response_time"] += metric.response_time
                
                if metric.response_time < ep_stats["min_response_time"]:
                    ep_stats["min_response_time"] = metric.response_time
                if metric.response_time > ep_stats["max_response_time"]:
                    ep_stats["max_response_time"] = metric.response_time
            else:
                ep_stats["failed_requests"] += 1
                
        except Exception as e:
            logger.error(f"Error updating endpoint stats: {e}")
    
    def _update_time_window_stats(self, metric: RequestMetric):
        """Update time window statistics (called with lock held)"""
        try:
            # Calculate which time window this metric belongs to
            window_start = metric.timestamp.replace(second=0, microsecond=0)
            window_key = window_start.isoformat()
            
            if window_key not in self._time_windows:
                self._time_windows[window_key] = TimeWindowStats(
                    window_start=window_start,
                    window_end=window_start + timedelta(minutes=1)
                )
            
            window_stats = self._time_windows[window_key]
            window_stats.total_requests += 1
            
            if metric.success:
                window_stats.successful_requests += 1
                window_stats.total_response_time += metric.response_time
                
                if metric.response_time < window_stats.min_response_time:
                    window_stats.min_response_time = metric.response_time
                if metric.response_time > window_stats.max_response_time:
                    window_stats.max_response_time = metric.response_time
            else:
                window_stats.failed_requests += 1
                
                if metric.status_code:
                    window_stats.error_count_by_code[metric.status_code] = \
                        window_stats.error_count_by_code.get(metric.status_code, 0) + 1
            
            # Clean up old windows (keep last 60 minutes)
            cutoff_time = metric.timestamp - timedelta(minutes=60)
            windows_to_remove = [
                key for key, window in self._time_windows.items()
                if window.window_start < cutoff_time
            ]
            for key in windows_to_remove:
                del self._time_windows[key]
                
        except Exception as e:
            logger.error(f"Error updating time window stats: {e}")
    
    async def _monitoring_loop(self):
        """Background monitoring loop for calculating derived statistics"""
        try:
            while self._is_running:
                try:
                    # Calculate derived statistics
                    self._calculate_derived_stats()
                    
                    # Wait before next calculation
                    await asyncio.sleep(1.0)  # Update every second
                    
                except Exception as e:
                    logger.error(f"Error in monitoring loop: {e}")
                    await asyncio.sleep(1.0)
                    
        except asyncio.CancelledError:
            logger.info(f"Statistics monitoring loop cancelled for session {self.session_id}")
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}")
    
    def _calculate_derived_stats(self):
        """Calculate derived statistics like RPS, percentiles, etc."""
        try:
            with self._lock:
                now = datetime.now()
                
                # Calculate current RPS (requests in last 10 seconds)
                recent_cutoff = now - timedelta(seconds=10)
                recent_requests = sum(
                    1 for metric in self._metrics
                    if metric.timestamp > recent_cutoff
                )
                self.stats.current_rps = recent_requests / 10.0
                
                # Update peak RPS
                if self.stats.current_rps > self.stats.peak_rps:
                    self.stats.peak_rps = self.stats.current_rps
                
                # Calculate error rate in last minute
                minute_cutoff = now - timedelta(minutes=1)
                minute_requests = [
                    metric for metric in self._metrics
                    if metric.timestamp > minute_cutoff
                ]
                
                if minute_requests:
                    minute_errors = sum(1 for metric in minute_requests if not metric.success)
                    self.stats.error_rate_last_minute = (minute_errors / len(minute_requests)) * 100
                else:
                    self.stats.error_rate_last_minute = 0.0
                
                # Calculate response time percentiles
                if self._response_times:
                    sorted_times = sorted(self._response_times)
                    count = len(sorted_times)
                    
                    self.stats.response_time_p50 = sorted_times[int(count * 0.5)]
                    self.stats.response_time_p95 = sorted_times[int(count * 0.95)]
                    self.stats.response_time_p99 = sorted_times[int(count * 0.99)]
                
        except Exception as e:
            logger.error(f"Error calculating derived stats: {e}")
    
    def add_update_callback(self, callback: Callable[[RealTimeStats], None]):
        """Add callback to be notified of statistics updates"""
        self._update_callbacks.append(callback)
    
    def remove_update_callback(self, callback: Callable[[RealTimeStats], None]):
        """Remove update callback"""
        if callback in self._update_callbacks:
            self._update_callbacks.remove(callback)
    
    def _notify_callbacks(self):
        """Notify all registered callbacks of statistics update"""
        try:
            for callback in self._update_callbacks:
                try:
                    callback(self.stats)
                except Exception as e:
                    logger.error(f"Error in statistics callback: {e}")
        except Exception as e:
            logger.error(f"Error notifying callbacks: {e}")
    
    def get_current_stats(self) -> RealTimeStats:
        """Get current real-time statistics"""
        with self._lock:
            return self.stats
    
    def get_time_window_stats(self, minutes: int = 10) -> List[TimeWindowStats]:
        """Get time window statistics for the last N minutes"""
        try:
            with self._lock:
                cutoff_time = datetime.now() - timedelta(minutes=minutes)
                
                return [
                    window for window in self._time_windows.values()
                    if window.window_start >= cutoff_time
                ]
        except Exception as e:
            logger.error(f"Error getting time window stats: {e}")
            return []
    
    def get_recent_metrics(self, count: int = 100) -> List[RequestMetric]:
        """Get recent request metrics"""
        try:
            with self._lock:
                return list(self._metrics)[-count:]
        except Exception as e:
            logger.error(f"Error getting recent metrics: {e}")
            return []
    
    def export_statistics(self, file_path: str):
        """Export statistics to JSON file"""
        try:
            with self._lock:
                export_data = {
                    "session_id": self.session_id,
                    "export_time": datetime.now().isoformat(),
                    "real_time_stats": self.stats.to_dict(),
                    "time_windows": [window.to_dict() for window in self._time_windows.values()],
                    "recent_metrics": [metric.to_dict() for metric in list(self._metrics)[-1000:]]
                }
            
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Statistics exported to {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting statistics: {e}")

class StatisticsManager:
    """
    Manages statistics collectors for multiple sessions
    """
    
    def __init__(self):
        self._collectors: Dict[str, StatisticsCollector] = {}
        self._lock = Lock()
    
    def create_collector(self, session_id: str) -> StatisticsCollector:
        """Create a new statistics collector for a session"""
        try:
            with self._lock:
                if session_id in self._collectors:
                    logger.warning(f"Statistics collector already exists for session {session_id}")
                    return self._collectors[session_id]
                
                collector = StatisticsCollector(session_id)
                self._collectors[session_id] = collector
                collector.start_monitoring()
                
                logger.info(f"Created statistics collector for session {session_id}")
                return collector
                
        except Exception as e:
            logger.error(f"Error creating statistics collector: {e}")
            raise
    
    async def remove_collector(self, session_id: str):
        """Remove and stop a statistics collector"""
        try:
            with self._lock:
                collector = self._collectors.pop(session_id, None)
            
            if collector:
                await collector.stop_monitoring()
                logger.info(f"Removed statistics collector for session {session_id}")
                
        except Exception as e:
            logger.error(f"Error removing statistics collector: {e}")
    
    def get_collector(self, session_id: str) -> Optional[StatisticsCollector]:
        """Get statistics collector for a session"""
        with self._lock:
            return self._collectors.get(session_id)
    
    def get_all_collectors(self) -> Dict[str, StatisticsCollector]:
        """Get all active statistics collectors"""
        with self._lock:
            return self._collectors.copy()
    
    async def cleanup_old_collectors(self, max_age_hours: int = 24):
        """Clean up old statistics collectors"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            collectors_to_remove = []
            
            with self._lock:
                for session_id, collector in self._collectors.items():
                    if collector.stats.start_time < cutoff_time:
                        collectors_to_remove.append(session_id)
            
            for session_id in collectors_to_remove:
                await self.remove_collector(session_id)
            
            if collectors_to_remove:
                logger.info(f"Cleaned up {len(collectors_to_remove)} old statistics collectors")
                
        except Exception as e:
            logger.error(f"Error cleaning up old collectors: {e}")

# Global statistics manager instance
statistics_manager = StatisticsManager()