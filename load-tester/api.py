"""
API endpoints for Load Testing Automation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from config import config_manager
from endpoint_selector import endpoint_selector
from statistics import statistics_manager
import load_test_manager as ltm_module
from error_handler import error_handler
from resource_monitor import resource_monitor

logger = logging.getLogger(__name__)

router = APIRouter()

class ConfigUpdateRequest(BaseModel):
    """Request model for configuration updates"""
    config: Dict[str, Any]

class WeightUpdateRequest(BaseModel):
    """Request model for endpoint weight updates"""
    weights: Dict[str, float]

class LoadTestStartRequest(BaseModel):
    """Request model for starting load test"""
    session_name: str
    concurrent_users: int = 10
    duration_minutes: int = 30
    request_interval_min: float = 1.0
    request_interval_max: float = 5.0
    endpoint_weights: Dict[str, float] = {}
    max_errors_per_minute: int = 100
    enable_logging: bool = True
    timeout: int = 30
    enable_user_login: bool = False

@router.get("/config")
async def get_config():
    """Get current configuration"""
    try:
        return {"config": config_manager.get_config()}
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get configuration")

@router.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration"""
    try:
        success = config_manager.update_config(request.config)
        if success:
            # Reset user session manager to reload configuration
            from user_session_manager import reset_user_session_manager
            reset_user_session_manager()
            return {"message": "Configuration updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Invalid configuration")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@router.get("/status")
async def get_status():
    """Get current load testing status"""
    try:
        if not ltm_module.load_test_manager:
            return {
                "status": "initializing",
                "active_sessions": 0,
                "message": "Load test manager not initialized"
            }
        
        active_sessions = ltm_module.load_test_manager.get_active_sessions()
        all_sessions = ltm_module.load_test_manager.get_all_sessions()
        
        status = "idle"
        if active_sessions:
            status = "running"
        
        return {
            "status": status,
            "active_sessions": len(active_sessions),
            "total_sessions": len(all_sessions),
            "message": f"Load testing service is {status}",
            "active_session_ids": [session.id for session in active_sessions]
        }
        
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return {
            "status": "error",
            "active_sessions": 0,
            "message": f"Error getting status: {str(e)}"
        }

@router.get("/endpoints")
async def get_endpoints():
    """Get all endpoint configurations and statistics"""
    try:
        return endpoint_selector.get_endpoint_summary()
    except Exception as e:
        logger.error(f"Error getting endpoints: {e}")
        raise HTTPException(status_code=500, detail="Failed to get endpoints")

@router.get("/endpoints/select")
async def select_endpoint():
    """Select a random endpoint based on weights"""
    try:
        selected = endpoint_selector.select_endpoint()
        if selected:
            return {
                "endpoint": {
                    "name": selected.name,
                    "url": selected.url,
                    "method": selected.method,
                    "weight": selected.weight,
                    "description": selected.description
                }
            }
        else:
            raise HTTPException(status_code=404, detail="No enabled endpoints available")
    except Exception as e:
        logger.error(f"Error selecting endpoint: {e}")
        raise HTTPException(status_code=500, detail="Failed to select endpoint")

@router.post("/endpoints/weights")
async def update_endpoint_weights(request: WeightUpdateRequest):
    """Update endpoint weights"""
    try:
        success = endpoint_selector.update_weights(request.weights)
        if success:
            return {"message": "Endpoint weights updated successfully"}
        else:
            raise HTTPException(status_code=400, detail="Failed to update weights")
    except Exception as e:
        logger.error(f"Error updating endpoint weights: {e}")
        raise HTTPException(status_code=500, detail="Failed to update endpoint weights")

@router.get("/endpoints/stats")
async def get_endpoint_stats():
    """Get endpoint statistics"""
    try:
        stats = endpoint_selector.get_endpoint_stats()
        return {
            "stats": {
                name: {
                    "total_requests": stat.total_requests,
                    "successful_requests": stat.successful_requests,
                    "failed_requests": stat.failed_requests,
                    "success_rate": stat.success_rate,
                    "average_response_time": stat.average_response_time,
                    "last_accessed": stat.last_accessed.isoformat() if stat.last_accessed else None
                }
                for name, stat in stats.items()
            }
        }
    except Exception as e:
        logger.error(f"Error getting endpoint stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get endpoint statistics")

@router.post("/endpoints/reload")
async def reload_endpoints():
    """Reload endpoint configurations"""
    try:
        endpoint_selector.reload_endpoints()
        return {"message": "Endpoints reloaded successfully"}
    except Exception as e:
        logger.error(f"Error reloading endpoints: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload endpoints")

@router.get("/statistics/{session_id}")
async def get_session_statistics(session_id: str):
    """Get real-time statistics for a session"""
    try:
        collector = statistics_manager.get_collector(session_id)
        if not collector:
            raise HTTPException(status_code=404, detail="Session statistics not found")
        
        stats = collector.get_current_stats()
        return {"statistics": stats.to_dict()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session statistics")

@router.get("/statistics/{session_id}/windows")
async def get_session_time_windows(session_id: str, minutes: int = 10):
    """Get time window statistics for a session"""
    try:
        collector = statistics_manager.get_collector(session_id)
        if not collector:
            raise HTTPException(status_code=404, detail="Session statistics not found")
        
        windows = collector.get_time_window_stats(minutes)
        return {
            "time_windows": [window.to_dict() for window in windows],
            "window_count": len(windows)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting time window statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get time window statistics")

@router.get("/statistics/{session_id}/metrics")
async def get_session_recent_metrics(session_id: str, count: int = 100):
    """Get recent request metrics for a session"""
    try:
        collector = statistics_manager.get_collector(session_id)
        if not collector:
            raise HTTPException(status_code=404, detail="Session statistics not found")
        
        metrics = collector.get_recent_metrics(count)
        return {
            "metrics": [metric.to_dict() for metric in metrics],
            "metric_count": len(metrics)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recent metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent metrics")

@router.get("/statistics")
async def get_all_statistics():
    """Get statistics for all active sessions"""
    try:
        collectors = statistics_manager.get_all_collectors()
        result = {}
        
        for session_id, collector in collectors.items():
            stats = collector.get_current_stats()
            result[session_id] = stats.to_dict()
        
        return {"sessions": result}
    except Exception as e:
        logger.error(f"Error getting all statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# Load Test Control Endpoints

@router.post("/load-test/start")
async def start_load_test(request: LoadTestStartRequest):
    """Start a new load test session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        from load_test_manager import LoadTestConfig
        config = LoadTestConfig(
            session_name=request.session_name,
            concurrent_users=request.concurrent_users,
            duration_minutes=request.duration_minutes,
            request_interval_min=request.request_interval_min,
            request_interval_max=request.request_interval_max,
            endpoint_weights=request.endpoint_weights,
            max_errors_per_minute=request.max_errors_per_minute,
            enable_logging=request.enable_logging,
            timeout=request.timeout,
            enable_user_login=request.enable_user_login
        )
        
        session = await ltm_module.load_test_manager.start_test(config)
        return {
            "message": "Load test started successfully",
            "session": session.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting load test: {e}")
        raise HTTPException(status_code=500, detail="Failed to start load test")

@router.post("/load-test/stop/{session_id}")
async def stop_load_test(session_id: str):
    """Stop a running load test session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        success = await ltm_module.load_test_manager.stop_test(session_id)
        if success:
            return {"message": f"Load test {session_id} stopped successfully"}
        else:
            raise HTTPException(status_code=404, detail="Session not found or not active")
            
    except Exception as e:
        logger.error(f"Error stopping load test {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop load test")

@router.post("/load-test/emergency-stop")
async def emergency_stop_load_test():
    """Emergency stop all active load test sessions"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        success = await ltm_module.load_test_manager.emergency_stop()
        if success:
            return {"message": "Emergency stop completed successfully"}
        else:
            raise HTTPException(status_code=500, detail="Emergency stop failed")
            
    except Exception as e:
        logger.error(f"Error during emergency stop: {e}")
        raise HTTPException(status_code=500, detail="Emergency stop failed")

@router.get("/load-test/status/{session_id}")
async def get_load_test_status(session_id: str):
    """Get status of a specific load test session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        status = ltm_module.load_test_manager.get_status(session_id)
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting load test status {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get load test status")

@router.get("/load-test/sessions")
async def get_all_sessions():
    """Get all load test sessions"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        sessions = ltm_module.load_test_manager.get_all_sessions()
        return {
            "sessions": [session.to_dict() for session in sessions],
            "total_count": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error getting all sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sessions")

@router.get("/load-test/sessions/active")
async def get_active_sessions():
    """Get currently active load test sessions"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        active_sessions = ltm_module.load_test_manager.get_active_sessions()
        return {
            "active_sessions": [session.to_dict() for session in active_sessions],
            "active_count": len(active_sessions)
        }
        
    except Exception as e:
        logger.error(f"Error getting active sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active sessions")

@router.delete("/load-test/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a load test session (only if not active)"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        success = ltm_module.load_test_manager.delete_session(session_id)
        if success:
            return {"message": f"Session {session_id} deleted successfully"}
        else:
            raise HTTPException(status_code=400, detail="Cannot delete active session or session not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete session")

@router.get("/load-test/sessions/{session_id}")
async def get_session_details(session_id: str):
    """Get detailed information about a specific session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        session = ltm_module.load_test_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Get statistics if available
        stats = None
        collector = statistics_manager.get_collector(session_id)
        if collector:
            stats = collector.get_current_stats().to_dict()
        
        return {
            "session": session.to_dict(),
            "statistics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session details {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get session details")

@router.post("/load-test/sessions/{session_id}/pause")
async def pause_session(session_id: str):
    """Pause a running load test session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        success = await ltm_module.load_test_manager.pause_test(session_id)
        if success:
            return {"message": f"Session {session_id} paused successfully"}
        else:
            raise HTTPException(status_code=400, detail="Cannot pause session - not found or not running")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to pause session")

@router.post("/load-test/sessions/{session_id}/resume")
async def resume_session(session_id: str):
    """Resume a paused load test session"""
    try:
        if not ltm_module.load_test_manager:
            raise HTTPException(status_code=503, detail="Load test manager not initialized")
        
        success = await ltm_module.load_test_manager.resume_test(session_id)
        if success:
            return {"message": f"Session {session_id} resumed successfully"}
        else:
            raise HTTPException(status_code=400, detail="Cannot resume session - not found or not paused")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to resume session")

# Error Handling and Safety Endpoints

@router.get("/errors/stats")
async def get_error_stats():
    """Get current error statistics"""
    try:
        if not ltm_module.load_test_manager:
            return error_handler.get_error_stats().to_dict()
        
        return ltm_module.load_test_manager.get_error_stats()
        
    except Exception as e:
        logger.error(f"Error getting error stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get error statistics")

@router.get("/errors/recent")
async def get_recent_errors(limit: int = 50):
    """Get recent errors"""
    try:
        recent_errors = error_handler.get_recent_errors(limit)
        return {
            "errors": [error.to_dict() for error in recent_errors],
            "error_count": len(recent_errors)
        }
        
    except Exception as e:
        logger.error(f"Error getting recent errors: {e}")
        raise HTTPException(status_code=500, detail="Failed to get recent errors")

@router.get("/errors/circuit-breakers")
async def get_circuit_breaker_status():
    """Get circuit breaker status for all endpoints"""
    try:
        return {
            "circuit_breakers": error_handler.get_circuit_breaker_status()
        }
        
    except Exception as e:
        logger.error(f"Error getting circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get circuit breaker status")

@router.post("/errors/circuit-breakers/{endpoint}/reset")
async def reset_circuit_breaker(endpoint: str):
    """Reset circuit breaker for specific endpoint"""
    try:
        error_handler.reset_circuit_breaker(endpoint)
        return {"message": f"Circuit breaker reset for endpoint {endpoint}"}
        
    except Exception as e:
        logger.error(f"Error resetting circuit breaker for {endpoint}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset circuit breaker")

@router.delete("/errors/history")
async def clear_error_history():
    """Clear error history"""
    try:
        error_handler.cleanup_old_errors(max_age_hours=0)  # Clear all
        return {"message": "Error history cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing error history: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear error history")

# Resource Monitoring Endpoints

@router.get("/resources/status")
async def get_resource_status():
    """Get current resource usage and status"""
    try:
        if not ltm_module.load_test_manager:
            return resource_monitor.get_resource_status()
        
        return ltm_module.load_test_manager.get_resource_status()
        
    except Exception as e:
        logger.error(f"Error getting resource status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource status")

@router.get("/resources/usage")
async def get_current_resource_usage():
    """Get current resource usage"""
    try:
        current_usage = resource_monitor.get_current_usage()
        if current_usage:
            return {"usage": current_usage.to_dict()}
        else:
            return {"usage": None, "message": "No resource usage data available"}
        
    except Exception as e:
        logger.error(f"Error getting current resource usage: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource usage")

@router.get("/resources/history")
async def get_resource_usage_history(minutes: int = 10):
    """Get resource usage history"""
    try:
        history = resource_monitor.get_usage_history(minutes)
        return {
            "history": [usage.to_dict() for usage in history],
            "history_count": len(history),
            "time_range_minutes": minutes
        }
        
    except Exception as e:
        logger.error(f"Error getting resource usage history: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource usage history")

@router.get("/resources/alerts")
async def get_active_resource_alerts():
    """Get active resource alerts"""
    try:
        alerts = resource_monitor.get_active_alerts()
        return {
            "alerts": [alert.to_dict() for alert in alerts],
            "alert_count": len(alerts)
        }
        
    except Exception as e:
        logger.error(f"Error getting resource alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource alerts")

@router.delete("/resources/alerts")
async def clear_resource_alerts():
    """Clear all active resource alerts"""
    try:
        resource_monitor.clear_alerts()
        return {"message": "Resource alerts cleared successfully"}
        
    except Exception as e:
        logger.error(f"Error clearing resource alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear resource alerts")

@router.get("/resources/thresholds")
async def get_resource_thresholds():
    """Get current resource monitoring thresholds"""
    try:
        return {"thresholds": resource_monitor.thresholds.to_dict()}
        
    except Exception as e:
        logger.error(f"Error getting resource thresholds: {e}")
        raise HTTPException(status_code=500, detail="Failed to get resource thresholds")

class ResourceThresholdUpdateRequest(BaseModel):
    """Request model for updating resource thresholds"""
    cpu_warning: float = None
    cpu_critical: float = None
    cpu_emergency: float = None
    memory_warning: float = None
    memory_critical: float = None
    memory_emergency: float = None
    network_warning: float = None
    network_critical: float = None
    network_emergency: float = None
    disk_warning: float = None
    disk_critical: float = None
    disk_emergency: float = None
    connections_warning: int = None
    connections_critical: int = None
    connections_emergency: int = None

@router.post("/resources/thresholds")
async def update_resource_thresholds(request: ResourceThresholdUpdateRequest):
    """Update resource monitoring thresholds"""
    try:
        from resource_monitor import ResourceThresholds
        
        # Get current thresholds
        current = resource_monitor.thresholds
        
        # Update only provided values
        new_thresholds = ResourceThresholds(
            cpu_warning=request.cpu_warning if request.cpu_warning is not None else current.cpu_warning,
            cpu_critical=request.cpu_critical if request.cpu_critical is not None else current.cpu_critical,
            cpu_emergency=request.cpu_emergency if request.cpu_emergency is not None else current.cpu_emergency,
            memory_warning=request.memory_warning if request.memory_warning is not None else current.memory_warning,
            memory_critical=request.memory_critical if request.memory_critical is not None else current.memory_critical,
            memory_emergency=request.memory_emergency if request.memory_emergency is not None else current.memory_emergency,
            network_warning=request.network_warning if request.network_warning is not None else current.network_warning,
            network_critical=request.network_critical if request.network_critical is not None else current.network_critical,
            network_emergency=request.network_emergency if request.network_emergency is not None else current.network_emergency,
            disk_warning=request.disk_warning if request.disk_warning is not None else current.disk_warning,
            disk_critical=request.disk_critical if request.disk_critical is not None else current.disk_critical,
            disk_emergency=request.disk_emergency if request.disk_emergency is not None else current.disk_emergency,
            connections_warning=request.connections_warning if request.connections_warning is not None else current.connections_warning,
            connections_critical=request.connections_critical if request.connections_critical is not None else current.connections_critical,
            connections_emergency=request.connections_emergency if request.connections_emergency is not None else current.connections_emergency
        )
        
        resource_monitor.update_thresholds(new_thresholds)
        return {"message": "Resource thresholds updated successfully"}
        
    except Exception as e:
        logger.error(f"Error updating resource thresholds: {e}")
        raise HTTPException(status_code=500, detail="Failed to update resource thresholds")

@router.get("/resources/connections")
async def get_connection_info():
    """Get connection limit and usage information"""
    try:
        return {
            "current_connections": resource_monitor.current_connections,
            "max_connections": resource_monitor.max_connections,
            "utilization_percent": (resource_monitor.current_connections / resource_monitor.max_connections * 100) if resource_monitor.max_connections > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting connection info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get connection information")

class ConnectionLimitRequest(BaseModel):
    """Request model for updating connection limit"""
    max_connections: int

@router.post("/resources/connections/limit")
async def set_connection_limit(request: ConnectionLimitRequest):
    """Set maximum connection limit"""
    try:
        if request.max_connections < 1:
            raise HTTPException(status_code=400, detail="Connection limit must be at least 1")
        
        resource_monitor.set_connection_limit(request.max_connections)
        return {"message": f"Connection limit set to {request.max_connections}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting connection limit: {e}")
        raise HTTPException(status_code=500, detail="Failed to set connection limit")

# Scheduling API Endpoints

class ScheduleCreateRequest(BaseModel):
    """Request model for creating scheduled load tests"""
    name: str
    schedule_type: str  # "one_time", "recurring", "cron"
    load_test_config: Dict[str, Any]
    start_time: Optional[str] = None  # ISO format datetime
    interval_minutes: Optional[int] = None
    max_executions: Optional[int] = None
    cron_expression: Optional[str] = None
    enabled: bool = True
    timezone: str = "UTC"

class ScheduleUpdateRequest(BaseModel):
    """Request model for updating scheduled load tests"""
    name: Optional[str] = None
    schedule_type: Optional[str] = None
    load_test_config: Optional[Dict[str, Any]] = None
    start_time: Optional[str] = None
    interval_minutes: Optional[int] = None
    max_executions: Optional[int] = None
    cron_expression: Optional[str] = None
    enabled: Optional[bool] = None
    timezone: Optional[str] = None

@router.get("/scheduler/status")
async def get_scheduler_status():
    """Get scheduler status and statistics"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            return {
                "running": False,
                "message": "Scheduler not initialized"
            }
        
        return scheduler.get_scheduler_status()
        
    except Exception as e:
        logger.error(f"Error getting scheduler status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get scheduler status")

@router.post("/scheduler/start")
async def start_scheduler():
    """Start the load test scheduler"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        await scheduler.start_scheduler()
        return {"message": "Scheduler started successfully"}
        
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")
        raise HTTPException(status_code=500, detail="Failed to start scheduler")

@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop the load test scheduler"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        await scheduler.stop_scheduler()
        return {"message": "Scheduler stopped successfully"}
        
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
        raise HTTPException(status_code=500, detail="Failed to stop scheduler")

@router.get("/schedules")
async def get_all_schedules():
    """Get all scheduled load tests"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        schedules = scheduler.get_all_schedules()
        return {
            "schedules": [schedule.to_dict() for schedule in schedules],
            "total_count": len(schedules)
        }
        
    except Exception as e:
        logger.error(f"Error getting schedules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schedules")

@router.get("/schedules/active")
async def get_active_schedules():
    """Get active scheduled load tests"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        schedules = scheduler.get_active_schedules()
        return {
            "active_schedules": [schedule.to_dict() for schedule in schedules],
            "active_count": len(schedules)
        }
        
    except Exception as e:
        logger.error(f"Error getting active schedules: {e}")
        raise HTTPException(status_code=500, detail="Failed to get active schedules")

@router.post("/schedules")
async def create_schedule(request: ScheduleCreateRequest):
    """Create a new scheduled load test"""
    try:
        from scheduler import get_scheduler, ScheduleConfig, ScheduleType
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        # Parse start_time if provided
        start_time = None
        if request.start_time:
            try:
                start_time = datetime.fromisoformat(request.start_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_time format. Use ISO format.")
        
        # Create schedule config
        config = ScheduleConfig(
            name=request.name,
            schedule_type=ScheduleType(request.schedule_type),
            load_test_config=request.load_test_config,
            start_time=start_time,
            interval_minutes=request.interval_minutes,
            max_executions=request.max_executions,
            cron_expression=request.cron_expression,
            enabled=request.enabled,
            timezone=request.timezone
        )
        
        # Create the scheduled task
        task = scheduler.create_schedule(config)
        
        return {
            "message": "Schedule created successfully",
            "schedule": task.to_dict()
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to create schedule")

@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: str):
    """Get a specific scheduled load test"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        schedule = scheduler.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"schedule": schedule.to_dict()}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get schedule")

@router.put("/schedules/{schedule_id}")
async def update_schedule(schedule_id: str, request: ScheduleUpdateRequest):
    """Update a scheduled load test"""
    try:
        from scheduler import get_scheduler, ScheduleConfig, ScheduleType
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        # Get existing schedule
        existing_task = scheduler.get_schedule(schedule_id)
        if not existing_task:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        # Create updated config
        config = existing_task.config
        
        if request.name is not None:
            config.name = request.name
        if request.schedule_type is not None:
            config.schedule_type = ScheduleType(request.schedule_type)
        if request.load_test_config is not None:
            config.load_test_config = request.load_test_config
        if request.start_time is not None:
            try:
                config.start_time = datetime.fromisoformat(request.start_time.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_time format. Use ISO format.")
        if request.interval_minutes is not None:
            config.interval_minutes = request.interval_minutes
        if request.max_executions is not None:
            config.max_executions = request.max_executions
        if request.cron_expression is not None:
            config.cron_expression = request.cron_expression
        if request.enabled is not None:
            config.enabled = request.enabled
        if request.timezone is not None:
            config.timezone = request.timezone
        
        # Update the schedule
        success = scheduler.update_schedule(schedule_id, config)
        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"message": "Schedule updated successfully"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update schedule")

@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str):
    """Delete a scheduled load test"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        success = scheduler.delete_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"message": f"Schedule {schedule_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete schedule")

@router.post("/schedules/{schedule_id}/enable")
async def enable_schedule(schedule_id: str):
    """Enable a scheduled load test"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        success = scheduler.enable_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"message": f"Schedule {schedule_id} enabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error enabling schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to enable schedule")

@router.post("/schedules/{schedule_id}/disable")
async def disable_schedule(schedule_id: str):
    """Disable a scheduled load test"""
    try:
        from scheduler import get_scheduler
        scheduler = get_scheduler()
        
        if not scheduler:
            raise HTTPException(status_code=503, detail="Scheduler not initialized")
        
        success = scheduler.disable_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found")
        
        return {"message": f"Schedule {schedule_id} disabled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error disabling schedule {schedule_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to disable schedule")

# Load Adjustment Endpoints

@router.get("/load-adjustment/status")
async def get_load_adjustment_status():
    """Get current load adjustment status"""
    try:
        from worker_pool import worker_pool
        return {
            "load_adjustment": worker_pool.get_load_adjustment_status(),
            "resource_monitoring": resource_monitor.is_monitoring
        }
        
    except Exception as e:
        logger.error(f"Error getting load adjustment status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get load adjustment status")

@router.post("/load-adjustment/reset")
async def reset_load_adjustments():
    """Reset all load adjustments to normal operation"""
    try:
        from worker_pool import worker_pool
        worker_pool.reset_load_adjustments()
        return {"message": "Load adjustments reset successfully"}
        
    except Exception as e:
        logger.error(f"Error resetting load adjustments: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset load adjustments")

# User Session Management API Endpoints

class TestUserRequest(BaseModel):
    """Request model for test user operations"""
    user_id: Optional[str] = Field(default=None, description="User ID (auto-generated if not provided)")
    username: str
    password: str
    enabled: bool = True
    description: str = ""

class TestUsersUpdateRequest(BaseModel):
    """Request model for updating all test users"""
    test_users: List[TestUserRequest]

@router.get("/users")
async def get_test_users():
    """Get all test users configuration"""
    try:
        from config import config_manager
        from user_session_manager import TestUser
        
        # Read directly from config to bypass any caching issues
        config = config_manager.get_config()
        users_config = config.get("test_users", [])
        
        print(f"DEBUG API: Raw config users: {users_config}")
        
        users = []
        for user_data in users_config:
            user = TestUser.from_dict(user_data)
            users.append(user)
            print(f"DEBUG API: Created user: {user.to_dict()}")
        
        result = {
            "test_users": [user.to_dict() for user in users],
            "total_count": len(users)
        }
        
        print(f"DEBUG API: Returning: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Error getting test users: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test users")

@router.post("/users")
async def add_test_user(request: TestUserRequest):
    """Add a new test user"""
    try:
        from user_session_manager import get_user_session_manager, TestUser
        import uuid
        manager = get_user_session_manager()
        
        # Generate unique user ID if not provided or empty
        user_id = request.user_id if request.user_id and request.user_id.strip() else f"user_{uuid.uuid4().hex[:8]}"
        
        # Check if user_id already exists and generate new one if needed
        existing_users = manager.get_test_users()
        existing_ids = {user.user_id for user in existing_users}
        
        while user_id in existing_ids:
            user_id = f"user_{uuid.uuid4().hex[:8]}"
        
        user = TestUser(
            user_id=user_id,
            username=request.username,
            password=request.password,
            enabled=request.enabled,
            description=request.description
        )
        
        success = manager.add_test_user(user)
        if success:
            # Update configuration file
            users = manager.get_test_users()
            manager.update_test_users_config(users)
            return {
                "message": f"Test user {request.username} added successfully",
                "user_id": user_id
            }
        else:
            raise HTTPException(status_code=400, detail="User already exists or invalid data")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding test user: {e}")
        raise HTTPException(status_code=500, detail="Failed to add test user")

@router.put("/users")
async def update_test_users(request: TestUsersUpdateRequest):
    """Update all test users configuration"""
    try:
        from user_session_manager import get_user_session_manager, TestUser
        manager = get_user_session_manager()
        
        # Convert request to TestUser objects
        users = []
        for user_req in request.test_users:
            user = TestUser(
                user_id=user_req.user_id,
                username=user_req.username,
                password=user_req.password,
                enabled=user_req.enabled,
                description=user_req.description
            )
            users.append(user)
        
        # Update configuration
        success = manager.update_test_users_config(users)
        if success:
            return {"message": f"Updated {len(users)} test users successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save test users configuration")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating test users: {e}")
        raise HTTPException(status_code=500, detail="Failed to update test users")

@router.delete("/users/{user_id}")
async def remove_test_user(user_id: str):
    """Remove a test user"""
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        success = manager.remove_test_user(user_id)
        if success:
            # Update configuration file
            users = manager.get_test_users()
            manager.update_test_users_config(users)
            return {"message": f"Test user {user_id} removed successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing test user: {e}")
        raise HTTPException(status_code=500, detail="Failed to remove test user")

@router.get("/users/sessions")
async def get_user_sessions():
    """Get current user session status"""
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        stats = manager.get_session_stats()
        active_sessions = manager.get_active_sessions()
        
        return {
            "session_stats": stats.to_dict(),
            "active_sessions": [session.to_dict() for session in active_sessions],
            "active_count": len(active_sessions)
        }
        
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user sessions")

@router.get("/test-simple")
async def test_simple():
    """Simple test endpoint"""
    print("DEBUG: Simple test endpoint called")
    return {"message": "Simple test working"}

@router.post("/users/sessions/login")
async def login_all_users():
    """Login all enabled test users"""
    print("DEBUG: Login endpoint called")  # Use print for debugging
    logger.info("API: Login endpoint called")
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        print(f"DEBUG: Manager has {len(manager.test_users)} users")
        print(f"DEBUG: Manager instance: {id(manager)}")
        
        logger.info(f"API: Starting login for {len(manager.test_users)} users")
        sessions = await manager.login_all_users()
        logger.info(f"API: Login completed with {len(sessions)} sessions")
        
        return {
            "message": f"Logged in {len(sessions)} users successfully",
            "sessions": {user_id: session.to_dict() for user_id, session in sessions.items()},
            "successful_logins": len(sessions)
        }
        
    except Exception as e:
        logger.error(f"Error logging in users: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to login users")

@router.post("/users/sessions/refresh")
async def refresh_expired_sessions():
    """Refresh expired user sessions"""
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        refreshed_count = await manager.refresh_expired_sessions()
        
        return {
            "message": f"Refreshed {refreshed_count} expired sessions",
            "refreshed_count": refreshed_count
        }
        
    except Exception as e:
        logger.error(f"Error refreshing sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh sessions")

@router.post("/users/sessions/logout")
async def logout_all_users():
    """Logout all users and clear sessions"""
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        logout_count = await manager.logout_all_users()
        
        return {
            "message": f"Logged out {logout_count} users successfully",
            "logout_count": logout_count
        }
        
    except Exception as e:
        logger.error(f"Error logging out users: {e}")
        raise HTTPException(status_code=500, detail="Failed to logout users")

@router.get("/users/sessions/random")
async def get_random_session():
    """Get a random active user session for testing"""
    try:
        from user_session_manager import get_user_session_manager
        manager = get_user_session_manager()
        
        session = manager.get_random_session()
        if session:
            return {"session": session.to_dict()}
        else:
            raise HTTPException(status_code=404, detail="No active sessions available")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting random session: {e}")
        raise HTTPException(status_code=500, detail="Failed to get random session")

@router.post("/users/sessions/reset")
async def reset_session_manager():
    """Reset user session manager to reload configuration"""
    try:
        from user_session_manager import reset_user_session_manager
        reset_user_session_manager()
        return {"message": "User session manager reset successfully"}
        
    except Exception as e:
        logger.error(f"Error resetting session manager: {e}")
        raise HTTPException(status_code=500, detail="Failed to reset session manager")