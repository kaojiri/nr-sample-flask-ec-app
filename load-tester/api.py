"""
API endpoints for Load Testing Automation
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

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

# User Sync API Endpoints

class UserImportRequest(BaseModel):
    """Request model for user import"""
    users: List[Dict[str, Any]]
    export_timestamp: str
    source_system: str
    total_count: int
    metadata: Dict[str, Any] = {}

@router.post("/users/import")
async def import_users(request: UserImportRequest):
    """Main Applicationからのユーザーデータをインポート"""
    try:
        from user_sync_api import UserSyncAPI
        
        data = request.dict()
        
        sync_api = UserSyncAPI()
        result = sync_api.import_users(data)
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f'Import API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/sync-status")
async def get_sync_status():
    """同期状況取得"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        status = sync_api.get_sync_status()
        return status
        
    except Exception as e:
        logger.error(f'Sync status API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/sessions/bulk-login")
async def bulk_login():
    """一括ログイン実行"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        result = sync_api.bulk_login_users()
        
        status_code = 200 if result.get("success", False) else 400
        return result
        
    except Exception as e:
        logger.error(f'Bulk login API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/health")
async def health_check():
    """ヘルスチェック"""
    from datetime import datetime
    return {
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'user_sync_api'
    }

@router.get("/users/debug/list")
async def debug_list_users():
    """デバッグ用: 全ユーザーリスト表示"""
    try:
        from user_session_manager import get_user_session_manager
        from datetime import datetime
        
        manager = get_user_session_manager()
        test_users = manager.get_test_users()
        
        users_info = []
        for user in test_users:
            users_info.append({
                "user_id": user.user_id,
                "username": user.username,
                "enabled": user.enabled,
                "description": user.description,
                "test_batch_id": getattr(user, 'test_batch_id', None),
                "is_bulk_created": getattr(user, 'is_bulk_created', False)
            })
        
        return {
            "total_users": len(users_info),
            "users": users_info,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f'Debug list users error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/debug/batches")
async def debug_list_batches():
    """デバッグ用: バッチ情報表示"""
    try:
        from user_session_manager import get_user_session_manager
        from datetime import datetime
        
        manager = get_user_session_manager()
        test_users = manager.get_test_users()
        
        # バッチごとにユーザーをグループ化
        batches = {}
        for user in test_users:
            batch_id = getattr(user, 'test_batch_id', None) or 'no_batch'
            if batch_id not in batches:
                batches[batch_id] = []
            batches[batch_id].append({
                "user_id": user.user_id,
                "username": user.username,
                "enabled": user.enabled
            })
        
        return {
            "total_batches": len(batches),
            "batches": batches,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f'Debug list batches error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

# バッチ管理エンドポイント

@router.get("/users/batches")
async def get_batch_info():
    """バッチ情報取得"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        batch_info = sync_api.get_batch_info()
        
        return batch_info
        
    except Exception as e:
        logger.error(f'Batch info API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/users/batches/{batch_id}/login")
async def login_batch_users(batch_id: str):
    """指定バッチのユーザーで一括ログイン"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        result = sync_api.login_batch(batch_id)
        
        status_code = 200 if result.get("success", False) else 400
        return result
        
    except Exception as e:
        logger.error(f'Batch login API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/users/batches/{batch_id}")
async def remove_batch_users(batch_id: str):
    """指定バッチのユーザーを削除"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        result = sync_api.remove_batch(batch_id)
        
        status_code = 200 if result.get("success", False) else 400
        return result
        
    except Exception as e:
        logger.error(f'Batch removal API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/users/batches/{batch_id}/stats")
async def get_batch_stats(batch_id: str):
    """指定バッチのセッション統計取得"""
    try:
        from user_session_manager import get_user_session_manager
        
        manager = get_user_session_manager()
        stats = manager.get_batch_session_stats(batch_id)
        
        return stats
        
    except Exception as e:
        logger.error(f'Batch stats API error: {str(e)}')
        raise HTTPException(status_code=500, detail="Internal server error")

# クリーンアップAPI

class CleanupRequest(BaseModel):
    """Request model for cleanup operations"""
    batch_id: str
    users_to_delete: List[Dict[str, Any]] = []
    source: str = "main_application"

@router.post("/users/cleanup")
async def cleanup_users(request: CleanupRequest):
    """Main Applicationからのクリーンアップリクエストを処理"""
    try:
        from user_sync_api import UserSyncAPI
        
        sync_api = UserSyncAPI()
        
        # バッチIDが指定されている場合はバッチ削除
        if request.batch_id and request.batch_id != "all":
            result = sync_api.remove_batch(request.batch_id)
        else:
            # 全ユーザークリーンアップ
            result = sync_api.cleanup_all_test_users()
        
        logger.info(f"Cleanup request from {request.source}: batch_id={request.batch_id}, result={result.get('success', False)}")
        
        return result
        
    except Exception as e:
        logger.error(f'Cleanup API error: {str(e)}')
        return {
            "success": False,
            "error": f"クリーンアップ処理エラー: {str(e)}",
            "timestamp": datetime.utcnow().isoformat()
        }

# 分散サービステスト API エンドポイント

class DistributedTestRequest(BaseModel):
    """分散サービステストリクエストモデル"""
    endpoint: str = Field(..., description="テストするエンドポイント (n-plus-one, slow-query, database-error)")
    user_id: int = Field(..., description="テスト用ユーザーID")
    call_type: str = Field(default="direct", description="呼び出しタイプ (direct, via_main_app)")
    parameters: Optional[Dict[str, Any]] = Field(default=None, description="追加パラメータ")
    timeout: Optional[int] = Field(default=30, description="タイムアウト時間（秒）")

class DistributedLoadTestRequest(BaseModel):
    """分散サービス負荷テストリクエストモデル"""
    test_scenario: str = Field(..., description="テストシナリオ名")
    concurrent_users: Optional[int] = Field(default=None, description="同時実行ユーザー数")
    duration_minutes: Optional[int] = Field(default=None, description="実行時間（分）")
    call_type: Optional[str] = Field(default=None, description="呼び出しタイプ")

@router.get("/distributed-service/status")
async def get_distributed_service_status():
    """分散サービスの状態を取得"""
    try:
        from distributed_service_client import DistributedServiceTestClient
        from config import config_manager
        import aiohttp
        import time
        
        config = config_manager.get_config()
        distributed_service_url = config.get("distributed_service", {}).get("base_url", "http://distributed-service:5000")
        main_app_url = config.get("main_app_distributed", {}).get("base_url", "http://web:5000")
        
        # 各エンドポイントの基本的な接続テスト
        status = {
            "distributed_service": {
                "url": distributed_service_url,
                "status": "unknown",
                "endpoints": {}
            },
            "main_app_distributed": {
                "url": main_app_url,
                "status": "unknown",
                "endpoints": {}
            }
        }
        
        # 分散サービスの接続テスト
        try:
            start_time = time.time()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.post(
                    f"{distributed_service_url}/performance/n-plus-one",
                    json={"user_id": 1, "operation": "n-plus-one"},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    if response.status == 200:
                        status["distributed_service"]["status"] = "connected"
                        status["distributed_service"]["last_response_time"] = response_time
                    else:
                        status["distributed_service"]["status"] = "error"
                        status["distributed_service"]["error"] = f"HTTP {response.status}"
                        status["distributed_service"]["last_response_time"] = response_time
        except Exception as e:
            status["distributed_service"]["status"] = "error"
            status["distributed_service"]["error"] = str(e)
        
        # メインアプリケーション経由の接続テスト
        try:
            start_time = time.time()
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
                async with session.post(
                    f"{main_app_url}/distributed/n-plus-one",
                    json={"user_id": 1, "operation": "n-plus-one"},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    # 302リダイレクトも成功とみなす（認証が必要な場合）
                    if response.status in [200, 302]:
                        status["main_app_distributed"]["status"] = "connected"
                        status["main_app_distributed"]["last_response_time"] = response_time
                    else:
                        status["main_app_distributed"]["status"] = "error"
                        status["main_app_distributed"]["error"] = f"HTTP {response.status}"
                        status["main_app_distributed"]["last_response_time"] = response_time
        except Exception as e:
            status["main_app_distributed"]["status"] = "error"
            status["main_app_distributed"]["error"] = str(e)
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting distributed service status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get distributed service status")

@router.post("/distributed-service/test")
async def run_distributed_service_test(request: DistributedTestRequest):
    """分散サービスの単発テストを実行"""
    try:
        from config import config_manager
        import aiohttp
        import time
        
        config = config_manager.get_config()
        
        # URL構築
        if request.call_type == "direct":
            base_url = config.get("distributed_service", {}).get("base_url", "http://distributed-service:5000")
            endpoint_path = config.get("distributed_service", {}).get("endpoints", {}).get(
                request.endpoint, f"/performance/{request.endpoint}"
            )
        elif request.call_type == "via_main_app":
            base_url = config.get("main_app_distributed", {}).get("base_url", "http://web:5000")
            endpoint_key = f"distributed-{request.endpoint}"
            endpoint_path = config.get("main_app_distributed", {}).get("endpoints", {}).get(
                endpoint_key, f"/distributed/{request.endpoint}"
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid call_type. Use 'direct' or 'via_main_app'")
        
        url = f"{base_url}{endpoint_path}"
        
        # リクエストデータ
        data = {
            "user_id": request.user_id,
            "operation": request.endpoint
        }
        if request.parameters:
            data.update(request.parameters)
        
        # HTTPリクエスト実行
        start_time = time.time()
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=request.timeout)) as session:
                async with session.post(
                    url,
                    json=data,
                    headers={"Content-Type": "application/json"}
                ) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        try:
                            response_data = await response.json()
                            result = {
                                "status": "success",
                                "response_time": response_time,
                                "data": response_data,
                                "status_code": response.status
                            }
                        except Exception:
                            result = {
                                "status": "error",
                                "response_time": response_time,
                                "error": "Invalid JSON response",
                                "status_code": response.status
                            }
                    elif response.status == 302 and request.call_type == "via_main_app":
                        # リダイレクトは認証が必要な場合の正常な応答
                        result = {
                            "status": "success",
                            "response_time": response_time,
                            "data": {"redirect": True, "message": "Redirected to login (authentication required)"},
                            "status_code": response.status
                        }
                    else:
                        response_text = await response.text()
                        result = {
                            "status": "error",
                            "response_time": response_time,
                            "error": f"HTTP {response.status}: {response_text}",
                            "status_code": response.status
                        }
        except Exception as e:
            result = {
                "status": "error",
                "response_time": (time.time() - start_time) * 1000,
                "error": str(e),
                "status_code": 0
            }
        
        return {
            "test_result": result,
            "endpoint": request.endpoint,
            "user_id": request.user_id,
            "call_type": request.call_type,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error running distributed service test: {e}")
        raise HTTPException(status_code=500, detail="Failed to run distributed service test")

@router.get("/distributed-service/scenarios")
async def get_distributed_test_scenarios():
    """利用可能な分散サービステストシナリオを取得"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        scenarios = config.get("distributed_service", {}).get("test_scenarios", {})
        
        return {
            "scenarios": scenarios,
            "scenario_count": len(scenarios)
        }
        
    except Exception as e:
        logger.error(f"Error getting distributed test scenarios: {e}")
        raise HTTPException(status_code=500, detail="Failed to get distributed test scenarios")

@router.post("/distributed-service/load-test")
async def start_distributed_load_test(request: DistributedLoadTestRequest):
    """分散サービスの負荷テストを開始"""
    try:
        from config import config_manager
        from distributed_test_scenarios import DistributedTestScenarios
        
        config = config_manager.get_config()
        scenarios_config = config.get("distributed_service", {}).get("test_scenarios", {})
        
        # デバッグ情報をログに出力
        logger.info(f"Available scenarios: {list(scenarios_config.keys())}")
        logger.info(f"Requested scenario: {request.test_scenario}")
        
        if request.test_scenario not in scenarios_config:
            available_scenarios = list(scenarios_config.keys())
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown test scenario: {request.test_scenario}. Available scenarios: {available_scenarios}"
            )
        
        scenario_config = scenarios_config[request.test_scenario].copy()
        
        # リクエストパラメータで設定を上書き
        if request.concurrent_users is not None:
            scenario_config["concurrent_users"] = request.concurrent_users
        if request.duration_minutes is not None:
            scenario_config["duration_minutes"] = request.duration_minutes
        if request.call_type is not None:
            scenario_config["call_type"] = request.call_type
        
        # 分散テストシナリオを実行
        test_scenarios = DistributedTestScenarios()
        
        # ScenarioConfigオブジェクトを作成
        from distributed_test_scenarios import ScenarioConfig, ScenarioType
        
        scenario_type_map = {
            "basic_distributed_tracing": ScenarioType.BASIC_DISTRIBUTED_TRACING,
            "n_plus_one_load_test": ScenarioType.N_PLUS_ONE_LOAD_TEST,
            "slow_query_load_test": ScenarioType.SLOW_QUERY_LOAD_TEST,
            "database_error_test": ScenarioType.DATABASE_ERROR_TEST,
            "concurrent_users_test": ScenarioType.CONCURRENT_USERS_TEST,
            "comprehensive_test": ScenarioType.COMPREHENSIVE_TEST
        }
        
        config_obj = ScenarioConfig(
            scenario_type=scenario_type_map[request.test_scenario],
            concurrent_users=scenario_config.get("concurrent_users", 10),
            duration_minutes=scenario_config.get("duration_minutes", 5),
            ramp_up_seconds=scenario_config.get("ramp_up_seconds", 30),
            request_interval_min=scenario_config.get("request_interval_min", 1.0),
            request_interval_max=scenario_config.get("request_interval_max", 3.0),
            call_type=scenario_config.get("call_type", "direct"),
            include_trace_headers=scenario_config.get("include_trace_headers", True),
            timeout_seconds=scenario_config.get("timeout_seconds", 30)
        )
        
        # シナリオに応じてテストを実行
        if request.test_scenario == "basic_distributed_tracing":
            result = await test_scenarios.basic_distributed_tracing_test(config_obj)
        elif request.test_scenario == "n_plus_one_load_test":
            result = await test_scenarios.n_plus_one_load_test(config_obj)
        elif request.test_scenario == "slow_query_load_test":
            result = await test_scenarios.slow_query_load_test(config_obj)
        elif request.test_scenario == "database_error_test":
            result = await test_scenarios.database_error_test(config_obj)
        elif request.test_scenario == "concurrent_users_test":
            result = await test_scenarios.concurrent_users_test(config_obj)
        elif request.test_scenario == "comprehensive_test":
            result = await test_scenarios.comprehensive_test(config_obj)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported test scenario: {request.test_scenario}")
        
        return {
            "message": f"Distributed load test '{request.test_scenario}' completed",
            "scenario": request.test_scenario,
            "config": scenario_config,
            "result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting distributed load test: {e}")
        raise HTTPException(status_code=500, detail="Failed to start distributed load test")

@router.get("/distributed-service/metrics")
async def get_distributed_service_metrics():
    """分散サービステストのメトリクスを取得"""
    try:
        # 分散サービステスト用の統計情報を収集
        from distributed_service_client import DistributedServiceTestClient
        from config import config_manager
        
        config = config_manager.get_config()
        
        # 基本的なメトリクス情報を返す
        metrics = {
            "service_urls": {
                "distributed_service": config.get("distributed_service", {}).get("base_url", ""),
                "main_app_distributed": config.get("main_app_distributed", {}).get("base_url", "")
            },
            "available_endpoints": {
                "distributed_service": config.get("distributed_service", {}).get("endpoints", {}),
                "main_app_distributed": config.get("main_app_distributed", {}).get("endpoints", {})
            },
            "test_scenarios": list(config.get("distributed_service", {}).get("test_scenarios", {}).keys()),
            "newrelic_integration": {
                "enabled": config.get("newrelic_verification", {}).get("enabled", False),
                "app_names": config.get("newrelic_verification", {}).get("app_names", [])
            }
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error getting distributed service metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get distributed service metrics")

@router.get("/distributed-service/newrelic-status")
async def get_newrelic_integration_status():
    """New Relic統合の状態を取得"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        newrelic_config = config.get("newrelic_verification", {})
        
        status = {
            "enabled": newrelic_config.get("enabled", False),
            "api_key_configured": bool(newrelic_config.get("api_key")),
            "account_id_configured": bool(newrelic_config.get("account_id")),
            "app_names": newrelic_config.get("app_names", []),
            "verification_timeout": newrelic_config.get("verification_timeout_seconds", 300),
            "retry_attempts": newrelic_config.get("retry_attempts", 3)
        }
        
        # New Relic検証機能が利用可能かチェック
        try:
            from newrelic_verification import NewRelicVerification
            verification = NewRelicVerification()
            status["verification_available"] = True
            status["last_check"] = datetime.now().isoformat()
        except ImportError:
            status["verification_available"] = False
            status["error"] = "NewRelic verification module not available"
        except Exception as e:
            status["verification_available"] = False
            status["error"] = str(e)
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting NewRelic integration status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get NewRelic integration status")

@router.post("/distributed-service/verify-newrelic")
async def verify_newrelic_traces():
    """New Relicでの分散トレーシングを検証"""
    try:
        from newrelic_verification import NewRelicVerification
        from config import config_manager
        
        config = config_manager.get_config()
        newrelic_config = config.get("newrelic_verification", {})
        
        if not newrelic_config.get("enabled", False):
            raise HTTPException(status_code=400, detail="NewRelic verification is not enabled")
        
        verification = NewRelicVerification()
        
        # 基本的な分散トレーシング検証を実行
        result = await verification.verify_distributed_tracing()
        
        return {
            "verification_result": result,
            "timestamp": datetime.now().isoformat()
        }
        
    except ImportError:
        raise HTTPException(status_code=503, detail="NewRelic verification module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying NewRelic traces: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify NewRelic traces")

# 分散サービス設定管理API

class DistributedServiceConfigRequest(BaseModel):
    """分散サービス設定更新リクエスト"""
    distributed_service: Optional[Dict[str, Any]] = None
    main_app_distributed: Optional[Dict[str, Any]] = None
    newrelic_verification: Optional[Dict[str, Any]] = None

@router.get("/distributed-service/config")
async def get_distributed_service_config():
    """分散サービス設定を取得"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        
        return {
            "distributed_service": config.get("distributed_service", {}),
            "main_app_distributed": config.get("main_app_distributed", {}),
            "newrelic_verification": config.get("newrelic_verification", {})
        }
        
    except Exception as e:
        logger.error(f"Error getting distributed service config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get distributed service config")

@router.post("/distributed-service/config")
async def update_distributed_service_config(request: DistributedServiceConfigRequest):
    """分散サービス設定を更新"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        
        # 設定を更新
        if request.distributed_service is not None:
            config["distributed_service"] = {**config.get("distributed_service", {}), **request.distributed_service}
        
        if request.main_app_distributed is not None:
            config["main_app_distributed"] = {**config.get("main_app_distributed", {}), **request.main_app_distributed}
        
        if request.newrelic_verification is not None:
            config["newrelic_verification"] = {**config.get("newrelic_verification", {}), **request.newrelic_verification}
        
        # 設定を保存
        success = config_manager.update_config(config)
        
        if success:
            return {
                "message": "Distributed service configuration updated successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating distributed service config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update distributed service config")

@router.get("/distributed-service/config/scenarios")
async def get_test_scenarios_config():
    """テストシナリオ設定を取得"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        scenarios = config.get("distributed_service", {}).get("test_scenarios", {})
        
        return {
            "test_scenarios": scenarios,
            "scenario_count": len(scenarios)
        }
        
    except Exception as e:
        logger.error(f"Error getting test scenarios config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get test scenarios config")

class TestScenarioConfigRequest(BaseModel):
    """テストシナリオ設定更新リクエスト"""
    test_scenarios: Dict[str, Dict[str, Any]]

@router.post("/distributed-service/config/scenarios")
async def update_test_scenarios_config(request: TestScenarioConfigRequest):
    """テストシナリオ設定を更新"""
    try:
        from config import config_manager
        
        config = config_manager.get_config()
        
        # 分散サービス設定が存在しない場合は作成
        if "distributed_service" not in config:
            config["distributed_service"] = {}
        
        # テストシナリオ設定を更新
        config["distributed_service"]["test_scenarios"] = request.test_scenarios
        
        # 設定を保存
        success = config_manager.update_config(config)
        
        if success:
            return {
                "message": "Test scenarios configuration updated successfully",
                "updated_scenarios": list(request.test_scenarios.keys()),
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save test scenarios configuration")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating test scenarios config: {e}")
        raise HTTPException(status_code=500, detail="Failed to update test scenarios config")