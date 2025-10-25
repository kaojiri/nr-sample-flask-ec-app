"""
Load Test Manager - Handles test sessions, execution control, and state management
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4
from pathlib import Path

from worker_pool import WorkerPool, WorkerConfig, PoolStatus
from config import config_manager
from statistics import StatisticsCollector, statistics_manager
from error_handler import error_handler, ErrorInfo
from resource_monitor import resource_monitor, ResourceAlert, LoadAdjustmentAction

logger = logging.getLogger(__name__)

class TestStatus(Enum):
    """Status of load test session"""
    PENDING = "pending"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class LoadTestConfig:
    """Configuration for load test session"""
    session_name: str
    concurrent_users: int = 10
    duration_minutes: int = 30
    request_interval_min: float = 1.0
    request_interval_max: float = 5.0
    endpoint_weights: Dict[str, float] = None
    max_errors_per_minute: int = 100
    enable_logging: bool = True
    timeout: int = 30
    enable_user_login: bool = False
    
    def __post_init__(self):
        if self.endpoint_weights is None:
            self.endpoint_weights = {}
    
    def to_worker_config(self) -> WorkerConfig:
        """Convert to WorkerConfig for worker pool"""
        return WorkerConfig(
            request_interval_min=self.request_interval_min,
            request_interval_max=self.request_interval_max,
            max_errors_per_minute=self.max_errors_per_minute,
            timeout=self.timeout,
            enable_logging=self.enable_logging,
            enable_user_login=self.enable_user_login
        )
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.session_name or not self.session_name.strip():
            errors.append("Session name is required")
        
        if self.concurrent_users < 1:
            errors.append("Concurrent users must be at least 1")
        
        if self.concurrent_users > 50:  # Safety limit
            errors.append("Concurrent users cannot exceed 50")
        
        if self.duration_minutes < 1:
            errors.append("Duration must be at least 1 minute")
        
        if self.duration_minutes > 120:  # Safety limit
            errors.append("Duration cannot exceed 120 minutes")
        
        if self.request_interval_min <= 0:
            errors.append("Minimum request interval must be positive")
        
        if self.request_interval_max <= self.request_interval_min:
            errors.append("Maximum request interval must be greater than minimum")
        
        if self.max_errors_per_minute < 1:
            errors.append("Max errors per minute must be at least 1")
        
        if self.timeout < 1:
            errors.append("Timeout must be at least 1 second")
        
        return errors

@dataclass
class TestSession:
    """Load test session with execution state and statistics"""
    id: str
    config: LoadTestConfig
    status: TestStatus = TestStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_time: datetime = None
    error_message: Optional[str] = None
    
    # Runtime statistics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get session duration in seconds"""
        if not self.start_time:
            return None
        
        end_time = self.end_time or datetime.now()
        return (end_time - self.start_time).total_seconds()
    
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
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status in [TestStatus.STARTING, TestStatus.RUNNING]
    
    @property
    def is_finished(self) -> bool:
        """Check if session has finished (completed, failed, or cancelled)"""
        return self.status in [TestStatus.COMPLETED, TestStatus.FAILED, TestStatus.CANCELLED]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        data = asdict(self)
        
        # Convert datetime objects to ISO strings
        if self.start_time:
            data['start_time'] = self.start_time.isoformat()
        if self.end_time:
            data['end_time'] = self.end_time.isoformat()
        if self.created_time:
            data['created_time'] = self.created_time.isoformat()
        
        # Convert enum to string
        data['status'] = self.status.value
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestSession':
        """Create session from dictionary"""
        # Convert ISO strings back to datetime objects
        if data.get('start_time'):
            data['start_time'] = datetime.fromisoformat(data['start_time'])
        if data.get('end_time'):
            data['end_time'] = datetime.fromisoformat(data['end_time'])
        if data.get('created_time'):
            data['created_time'] = datetime.fromisoformat(data['created_time'])
        
        # Convert string back to enum
        if 'status' in data:
            data['status'] = TestStatus(data['status'])
        
        # Reconstruct LoadTestConfig
        if 'config' in data:
            config_data = data['config']
            data['config'] = LoadTestConfig(**config_data)
        
        return cls(**data)

class SessionPersistence:
    """Handles persistence of test sessions to disk"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.sessions_file = self.data_dir / "sessions.json"
    
    def save_session(self, session: TestSession):
        """Save a single session"""
        try:
            sessions = self.load_all_sessions()
            sessions[session.id] = session.to_dict()
            
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f, indent=2, default=str)
                
            logger.debug(f"Saved session {session.id}")
            
        except Exception as e:
            logger.error(f"Error saving session {session.id}: {e}")
    
    def load_session(self, session_id: str) -> Optional[TestSession]:
        """Load a specific session"""
        try:
            sessions = self.load_all_sessions()
            session_data = sessions.get(session_id)
            
            if session_data:
                return TestSession.from_dict(session_data)
            return None
            
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}")
            return None
    
    def load_all_sessions(self) -> Dict[str, Dict]:
        """Load all sessions from disk"""
        try:
            if not self.sessions_file.exists():
                return {}
            
            with open(self.sessions_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            return {}
    
    def delete_session(self, session_id: str):
        """Delete a session from persistence"""
        try:
            sessions = self.load_all_sessions()
            if session_id in sessions:
                del sessions[session_id]
                
                with open(self.sessions_file, 'w') as f:
                    json.dump(sessions, f, indent=2, default=str)
                    
                logger.debug(f"Deleted session {session_id}")
                
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
    
    def cleanup_old_sessions(self, max_age_days: int = 30):
        """Remove sessions older than specified days"""
        try:
            sessions = self.load_all_sessions()
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            
            sessions_to_delete = []
            for session_id, session_data in sessions.items():
                try:
                    created_time = datetime.fromisoformat(session_data.get('created_time', ''))
                    if created_time < cutoff_date:
                        sessions_to_delete.append(session_id)
                except (ValueError, TypeError):
                    # Invalid date format, mark for deletion
                    sessions_to_delete.append(session_id)
            
            for session_id in sessions_to_delete:
                del sessions[session_id]
            
            if sessions_to_delete:
                with open(self.sessions_file, 'w') as f:
                    json.dump(sessions, f, indent=2, default=str)
                
                logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")
                
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")

class LoadTestManager:
    """
    Main manager for load test sessions - handles session lifecycle,
    execution control, and state management
    """
    
    def __init__(self, worker_pool: WorkerPool):
        self.worker_pool = worker_pool
        self.sessions: Dict[str, TestSession] = {}
        self.active_session: Optional[TestSession] = None
        self.persistence = SessionPersistence()
        self._monitoring_task: Optional[asyncio.Task] = None
        self._statistics_collector: Optional[StatisticsCollector] = None
        
        # Error and resource monitoring
        self._error_callback_registered = False
        self._resource_callback_registered = False
        
        self._load_persisted_sessions()
    
    def _load_persisted_sessions(self):
        """Load persisted sessions on startup"""
        try:
            sessions_data = self.persistence.load_all_sessions()
            for session_id, session_data in sessions_data.items():
                try:
                    session = TestSession.from_dict(session_data)
                    self.sessions[session_id] = session
                    
                    # Reset active sessions to stopped state on startup
                    if session.is_active:
                        session.status = TestStatus.CANCELLED
                        session.end_time = datetime.now()
                        session.error_message = "Session interrupted by service restart"
                        self.persistence.save_session(session)
                        
                except Exception as e:
                    logger.error(f"Error loading persisted session {session_id}: {e}")
            
            logger.info(f"Loaded {len(self.sessions)} persisted sessions")
            
        except Exception as e:
            logger.error(f"Error loading persisted sessions: {e}")
    
    async def start_test(self, config: LoadTestConfig) -> TestSession:
        """
        Start a new load test session
        
        Args:
            config: Load test configuration
            
        Returns:
            TestSession object
            
        Raises:
            ValueError: If configuration is invalid or another test is running
        """
        try:
            # Validate configuration
            errors = config.validate()
            if errors:
                raise ValueError(f"Invalid configuration: {', '.join(errors)}")
            
            # Check if another test is already running
            if self.active_session and self.active_session.is_active:
                raise ValueError(f"Another test session is already running: {self.active_session.id}")
            
            # Create new session
            session_id = f"session-{uuid4().hex[:8]}"
            session = TestSession(
                id=session_id,
                config=config,
                status=TestStatus.STARTING
            )
            
            self.sessions[session_id] = session
            self.active_session = session
            
            # Persist session
            self.persistence.save_session(session)
            
            logger.info(f"Starting load test session {session_id}")
            
            # Apply endpoint weights if specified
            if config.endpoint_weights:
                from endpoint_selector import endpoint_selector
                endpoint_selector.update_weights(config.endpoint_weights)
            
            # Initialize user sessions if user login is enabled
            if config.enable_user_login:
                await self._initialize_user_sessions()
            
            # Create statistics collector for this session
            self._statistics_collector = statistics_manager.create_collector(session_id)
            
            # Start resource monitoring
            await resource_monitor.start_monitoring()
            
            # Register error and resource callbacks
            self._register_callbacks()
            
            # Start worker pool
            worker_config = config.to_worker_config()
            await self.worker_pool.start_workers(config.concurrent_users, worker_config)
            
            # Set statistics callback for workers
            self.worker_pool.set_statistics_callback(self._statistics_collector.record_request)
            
            # Update session status
            session.status = TestStatus.RUNNING
            session.start_time = datetime.now()
            self.persistence.save_session(session)
            
            # Start monitoring task
            self._monitoring_task = asyncio.create_task(
                self._monitor_session(session)
            )
            
            logger.info(f"Load test session {session_id} started successfully")
            return session
            
        except Exception as e:
            # Clean up on error
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.status = TestStatus.FAILED
                session.error_message = str(e)
                session.end_time = datetime.now()
                self.persistence.save_session(session)
                
                if self.active_session and self.active_session.id == session_id:
                    self.active_session = None
            
            logger.error(f"Error starting load test: {e}")
            raise
    
    async def stop_test(self, session_id: str) -> bool:
        """
        Stop a running load test session
        
        Args:
            session_id: ID of session to stop
            
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return False
            
            if not session.is_active:
                logger.warning(f"Session {session_id} is not active")
                return False
            
            logger.info(f"Stopping load test session {session_id}")
            
            # Update session status
            session.status = TestStatus.STOPPING
            self.persistence.save_session(session)
            
            # Stop worker pool
            await self.worker_pool.stop_workers()
            
            # Cancel monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Stop statistics collection
            if self._statistics_collector:
                await statistics_manager.remove_collector(session_id)
                self._statistics_collector = None
            
            # Stop resource monitoring
            await resource_monitor.stop_monitoring()
            
            # Unregister callbacks
            self._unregister_callbacks()
            
            # Update final session state
            session.status = TestStatus.COMPLETED
            session.end_time = datetime.now()
            self._update_session_stats(session)
            self.persistence.save_session(session)
            
            if self.active_session and self.active_session.id == session_id:
                self.active_session = None
            
            logger.info(f"Load test session {session_id} stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            
            # Mark session as failed
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.status = TestStatus.FAILED
                session.error_message = str(e)
                session.end_time = datetime.now()
                self.persistence.save_session(session)
            
            return False
    
    async def emergency_stop(self) -> bool:
        """
        Emergency stop all active sessions immediately
        
        Returns:
            True if stopped successfully, False otherwise
        """
        try:
            logger.warning("Emergency stop requested")
            
            # Stop worker pool immediately
            await self.worker_pool.emergency_stop()
            
            # Cancel monitoring task
            if self._monitoring_task and not self._monitoring_task.done():
                self._monitoring_task.cancel()
                try:
                    await self._monitoring_task
                except asyncio.CancelledError:
                    pass
            
            # Stop statistics collection
            if self._statistics_collector and self.active_session:
                await statistics_manager.remove_collector(self.active_session.id)
                self._statistics_collector = None
            
            # Update active session status
            if self.active_session and self.active_session.is_active:
                self.active_session.status = TestStatus.CANCELLED
                self.active_session.end_time = datetime.now()
                self.active_session.error_message = "Emergency stop requested"
                self._update_session_stats(self.active_session)
                self.persistence.save_session(self.active_session)
                self.active_session = None
            
            logger.info("Emergency stop completed")
            return True
            
        except Exception as e:
            logger.error(f"Error during emergency stop: {e}")
            return False
    
    async def pause_test(self, session_id: str) -> bool:
        """
        Pause a running load test session
        
        Args:
            session_id: ID of session to pause
            
        Returns:
            True if paused successfully, False otherwise
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return False
            
            if session.status != TestStatus.RUNNING:
                logger.warning(f"Session {session_id} is not running (status: {session.status})")
                return False
            
            logger.info(f"Pausing load test session {session_id}")
            
            # Pause worker pool
            await self.worker_pool.pause_workers()
            
            # Update session status
            session.status = TestStatus.PENDING  # Use PENDING to indicate paused state
            self.persistence.save_session(session)
            
            logger.info(f"Load test session {session_id} paused successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error pausing session {session_id}: {e}")
            return False
    
    async def resume_test(self, session_id: str) -> bool:
        """
        Resume a paused load test session
        
        Args:
            session_id: ID of session to resume
            
        Returns:
            True if resumed successfully, False otherwise
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return False
            
            if session.status != TestStatus.PENDING:
                logger.warning(f"Session {session_id} is not paused (status: {session.status})")
                return False
            
            logger.info(f"Resuming load test session {session_id}")
            
            # Resume worker pool
            await self.worker_pool.resume_workers()
            
            # Update session status
            session.status = TestStatus.RUNNING
            self.persistence.save_session(session)
            
            logger.info(f"Load test session {session_id} resumed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error resuming session {session_id}: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[TestSession]:
        """
        Get a specific session by ID
        
        Args:
            session_id: ID of session to retrieve
            
        Returns:
            TestSession object or None if not found
        """
        return self.sessions.get(session_id)
    
    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific session
        
        Args:
            session_id: ID of session
            
        Returns:
            Dictionary with session status and statistics
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                return None
            
            # Update statistics if session is active
            if session.is_active:
                self._update_session_stats(session)
            
            # Get worker pool statistics
            pool_stats = self.worker_pool.get_pool_stats()
            
            # Get real-time statistics if available
            real_time_stats = None
            statistics_collector = statistics_manager.get_collector(session_id)
            if statistics_collector:
                real_time_stats = statistics_collector.get_current_stats().to_dict()
            
            return {
                "session": session.to_dict(),
                "worker_pool": pool_stats,
                "real_time_stats": real_time_stats,
                "is_active": session.is_active,
                "duration_seconds": session.duration_seconds
            }
            
        except Exception as e:
            logger.error(f"Error getting session status {session_id}: {e}")
            return None
    
    def get_active_sessions(self) -> List[TestSession]:
        """Get list of currently active sessions"""
        return [
            session for session in self.sessions.values()
            if session.is_active
        ]
    
    def get_all_sessions(self) -> List[TestSession]:
        """Get list of all sessions"""
        return list(self.sessions.values())
    
    def get_session_history(self, limit: int = 50) -> List[TestSession]:
        """Get recent session history"""
        sessions = sorted(
            self.sessions.values(),
            key=lambda s: s.created_time,
            reverse=True
        )
        return sessions[:limit]
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session (only if not active)
        
        Args:
            session_id: ID of session to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            session = self.sessions.get(session_id)
            if not session:
                return False
            
            if session.is_active:
                logger.warning(f"Cannot delete active session {session_id}")
                return False
            
            del self.sessions[session_id]
            self.persistence.delete_session(session_id)
            
            logger.info(f"Deleted session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")
            return False
    
    async def _monitor_session(self, session: TestSession):
        """Monitor session execution and handle duration limits"""
        try:
            duration_seconds = session.config.duration_minutes * 60
            end_time = datetime.now() + timedelta(seconds=duration_seconds)
            
            logger.info(f"Monitoring session {session.id} for {duration_seconds} seconds")
            
            while datetime.now() < end_time and session.is_active:
                # Update session statistics
                self._update_session_stats(session)
                self.persistence.save_session(session)
                
                # Check if worker pool failed
                if self.worker_pool.status == PoolStatus.ERROR:
                    session.status = TestStatus.FAILED
                    session.error_message = "Worker pool encountered an error"
                    break
                
                # Wait before next check
                await asyncio.sleep(5.0)
            
            # Session duration completed or stopped
            if session.is_active:
                logger.info(f"Session {session.id} duration completed")
                await self.stop_test(session.id)
                
        except asyncio.CancelledError:
            logger.info(f"Monitoring cancelled for session {session.id}")
        except Exception as e:
            logger.error(f"Error monitoring session {session.id}: {e}")
            session.status = TestStatus.FAILED
            session.error_message = str(e)
            session.end_time = datetime.now()
            self.persistence.save_session(session)
    
    def _update_session_stats(self, session: TestSession):
        """Update session statistics from statistics collector and worker pool"""
        try:
            # Get statistics from collector if available
            statistics_collector = statistics_manager.get_collector(session.id)
            if statistics_collector:
                real_time_stats = statistics_collector.get_current_stats()
                session.total_requests = real_time_stats.total_requests
                session.successful_requests = real_time_stats.successful_requests
                session.failed_requests = real_time_stats.failed_requests
                session.total_response_time = real_time_stats.total_response_time
            else:
                # Fallback to worker pool stats
                pool_stats = self.worker_pool.get_pool_stats()
                session.total_requests = pool_stats.get('total_requests', 0)
                session.successful_requests = pool_stats.get('successful_requests', 0)
                session.failed_requests = pool_stats.get('failed_requests', 0)
                session.total_response_time = pool_stats.get('average_response_time', 0.0) * session.successful_requests
            
        except Exception as e:
            logger.error(f"Error updating session stats: {e}")
    
    async def cleanup_old_sessions(self, max_age_days: int = 30):
        """Clean up old sessions from memory and disk"""
        try:
            # Clean up from persistence
            self.persistence.cleanup_old_sessions(max_age_days)
            
            # Clean up from memory
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
            sessions_to_remove = []
            
            for session_id, session in self.sessions.items():
                if session.created_time < cutoff_date and session.is_finished:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                del self.sessions[session_id]
            
            if sessions_to_remove:
                logger.info(f"Cleaned up {len(sessions_to_remove)} old sessions from memory")
                
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")
    
    def _register_callbacks(self):
        """Register error and resource monitoring callbacks"""
        try:
            if not self._error_callback_registered:
                error_handler.add_error_callback(self._handle_error)
                self._error_callback_registered = True
            
            if not self._resource_callback_registered:
                resource_monitor.add_alert_callback(self._handle_resource_alert)
                self._resource_callback_registered = True
                
            logger.debug("Registered error and resource callbacks")
            
        except Exception as e:
            logger.error(f"Error registering callbacks: {e}")
    
    def _unregister_callbacks(self):
        """Unregister error and resource monitoring callbacks"""
        try:
            if self._error_callback_registered:
                error_handler.remove_error_callback(self._handle_error)
                self._error_callback_registered = False
            
            if self._resource_callback_registered:
                resource_monitor.remove_alert_callback(self._handle_resource_alert)
                self._resource_callback_registered = False
                
            logger.debug("Unregistered error and resource callbacks")
            
        except Exception as e:
            logger.error(f"Error unregistering callbacks: {e}")
    
    def _handle_error(self, error_info: ErrorInfo):
        """Handle error notifications from error handler"""
        try:
            if self.active_session:
                # Log error in session context
                logger.warning(f"Session {self.active_session.id} error: {error_info.message}")
                
                # Check if we should stop the test due to errors
                if not error_handler.should_continue_test():
                    logger.error("Stopping test due to high error rate")
                    asyncio.create_task(self.stop_test(self.active_session.id))
                    
        except Exception as e:
            logger.error(f"Error handling error callback: {e}")
    
    def _handle_resource_alert(self, alert: ResourceAlert):
        """Handle resource alerts from resource monitor"""
        try:
            if self.active_session:
                logger.warning(f"Session {self.active_session.id} resource alert: {alert.message}")
                
                # For critical/emergency alerts, consider stopping the test
                if alert.status.value in ['critical', 'emergency']:
                    logger.error(f"Critical resource alert: {alert.message}")
                    
                    # Emergency resource situations should stop the test
                    if alert.status.value == 'emergency':
                        logger.error("Emergency stopping test due to resource exhaustion")
                        asyncio.create_task(self.emergency_stop())
                        
        except Exception as e:
            logger.error(f"Error handling resource alert: {e}")
    
    async def _initialize_user_sessions(self):
        """Initialize user sessions for load testing"""
        try:
            from user_session_manager import get_user_session_manager
            manager = get_user_session_manager()
            
            logger.info("Initializing user sessions for load testing")
            
            # Login all enabled users
            sessions = await manager.login_all_users()
            
            if not sessions:
                logger.warning("No user sessions available - load test will run without authentication")
                return
            
            logger.info(f"Successfully initialized {len(sessions)} user sessions")
            
            # Optionally refresh expired sessions periodically during the test
            # This could be implemented as a background task if needed
            
        except Exception as e:
            logger.error(f"Error initializing user sessions: {e}")
            # Don't fail the load test if user sessions can't be initialized
            # The test will continue without authentication
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get current error statistics"""
        try:
            error_stats = error_handler.get_error_stats()
            recent_errors = error_handler.get_recent_errors(limit=10)
            
            return {
                "error_stats": error_stats.to_dict(),
                "recent_errors": [error.to_dict() for error in recent_errors],
                "circuit_breakers": error_handler.get_circuit_breaker_status()
            }
            
        except Exception as e:
            logger.error(f"Error getting error stats: {e}")
            return {"error": str(e)}
    
    def get_resource_status(self) -> Dict[str, Any]:
        """Get current resource status"""
        try:
            return resource_monitor.get_resource_status()
        except Exception as e:
            logger.error(f"Error getting resource status: {e}")
            return {"error": str(e)}

# Global load test manager instance will be initialized in main.py
load_test_manager: Optional[LoadTestManager] = None