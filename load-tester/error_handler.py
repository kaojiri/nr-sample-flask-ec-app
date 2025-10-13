"""
Comprehensive Error Handling System for Load Testing Automation
"""
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import aiohttp
import psutil
import traceback

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Types of errors that can occur during load testing"""
    NETWORK_ERROR = "network_error"
    HTTP_ERROR = "http_error"
    TIMEOUT_ERROR = "timeout_error"
    CONNECTION_ERROR = "connection_error"
    APPLICATION_ERROR = "application_error"
    RESOURCE_ERROR = "resource_error"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN_ERROR = "unknown_error"

class ErrorSeverity(Enum):
    """Severity levels for errors"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class ErrorAction(Enum):
    """Actions to take when errors occur"""
    CONTINUE = "continue"
    RETRY = "retry"
    THROTTLE = "throttle"
    STOP_WORKER = "stop_worker"
    STOP_TEST = "stop_test"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class ErrorInfo:
    """Information about an error occurrence"""
    error_type: ErrorType
    severity: ErrorSeverity
    message: str
    timestamp: datetime
    endpoint: Optional[str] = None
    worker_id: Optional[str] = None
    status_code: Optional[int] = None
    response_time: Optional[float] = None
    exception_type: Optional[str] = None
    stack_trace: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error info to dictionary"""
        return {
            "error_type": self.error_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "endpoint": self.endpoint,
            "worker_id": self.worker_id,
            "status_code": self.status_code,
            "response_time": self.response_time,
            "exception_type": self.exception_type,
            "stack_trace": self.stack_trace
        }

@dataclass
class ErrorStats:
    """Statistics about errors over time"""
    total_errors: int = 0
    errors_by_type: Dict[ErrorType, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_severity: Dict[ErrorSeverity, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_endpoint: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_last_minute: int = 0
    errors_last_hour: int = 0
    error_rate_per_minute: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error stats to dictionary"""
        return {
            "total_errors": self.total_errors,
            "errors_by_type": {k.value: v for k, v in self.errors_by_type.items()},
            "errors_by_severity": {k.value: v for k, v in self.errors_by_severity.items()},
            "errors_by_endpoint": dict(self.errors_by_endpoint),
            "errors_last_minute": self.errors_last_minute,
            "errors_last_hour": self.errors_last_hour,
            "error_rate_per_minute": self.error_rate_per_minute
        }

class CircuitBreaker:
    """Circuit breaker pattern implementation for error handling"""
    
    def __init__(self, 
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs):
        """Call function with circuit breaker protection"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    async def async_call(self, func: Callable, *args, **kwargs):
        """Async version of circuit breaker call"""
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """Check if circuit breaker should attempt reset"""
        if not self.last_failure_time:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() > self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        self.state = "closed"
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"

class BackoffStrategy:
    """Exponential backoff strategy for retries"""
    
    def __init__(self, 
                 initial_delay: float = 1.0,
                 max_delay: float = 60.0,
                 multiplier: float = 2.0,
                 jitter: bool = True):
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.attempt_count = 0
    
    def get_delay(self) -> float:
        """Get delay for current attempt"""
        delay = min(self.initial_delay * (self.multiplier ** self.attempt_count), self.max_delay)
        
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # Add 0-50% jitter
        
        self.attempt_count += 1
        return delay
    
    def reset(self):
        """Reset attempt count"""
        self.attempt_count = 0

class ErrorHandler:
    """
    Comprehensive error handler for load testing operations
    """
    
    def __init__(self, max_error_history: int = 1000):
        self.max_error_history = max_error_history
        self.error_history: deque = deque(maxlen=max_error_history)
        self.error_timestamps: deque = deque(maxlen=max_error_history)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.backoff_strategies: Dict[str, BackoffStrategy] = {}
        self.error_callbacks: List[Callable] = []
        
        # Error thresholds
        self.max_errors_per_minute = 100
        self.max_error_rate = 0.5  # 50% error rate
        self.critical_error_threshold = 10  # Critical errors in 1 minute
        
    def handle_network_error(self, error: Exception, context: Dict[str, Any]) -> ErrorAction:
        """
        Handle network-related errors
        
        Args:
            error: The network error that occurred
            context: Context information (endpoint, worker_id, etc.)
            
        Returns:
            ErrorAction to take
        """
        try:
            error_info = self._create_error_info(
                error_type=ErrorType.NETWORK_ERROR,
                severity=ErrorSeverity.MEDIUM,
                message=str(error),
                context=context,
                exception=error
            )
            
            self._record_error(error_info)
            
            # Determine action based on error type
            if isinstance(error, (aiohttp.ClientConnectionError, ConnectionError)):
                # Connection errors - retry with backoff
                return self._handle_connection_error(error_info, context)
            elif isinstance(error, (asyncio.TimeoutError, aiohttp.ServerTimeoutError)):
                # Timeout errors - throttle and retry
                return self._handle_timeout_error(error_info, context)
            else:
                # Other network errors - continue with throttling
                return ErrorAction.THROTTLE
                
        except Exception as e:
            logger.error(f"Error in network error handler: {e}")
            return ErrorAction.CONTINUE
    
    def handle_http_error(self, response_info: Dict[str, Any], context: Dict[str, Any]) -> ErrorAction:
        """
        Handle HTTP error responses
        
        Args:
            response_info: Information about the HTTP response
            context: Context information
            
        Returns:
            ErrorAction to take
        """
        try:
            status_code = response_info.get('status_code', 0)
            
            # Determine severity based on status code
            if status_code >= 500:
                severity = ErrorSeverity.HIGH
            elif status_code >= 400:
                severity = ErrorSeverity.MEDIUM
            else:
                severity = ErrorSeverity.LOW
            
            error_info = self._create_error_info(
                error_type=ErrorType.HTTP_ERROR,
                severity=severity,
                message=f"HTTP {status_code}: {response_info.get('reason', 'Unknown')}",
                context=context,
                status_code=status_code
            )
            
            self._record_error(error_info)
            
            # Determine action based on status code
            if status_code >= 500:
                # Server errors - retry with backoff
                return self._handle_server_error(error_info, context)
            elif status_code == 429:
                # Rate limiting - throttle heavily
                return ErrorAction.THROTTLE
            elif status_code >= 400:
                # Client errors - continue (likely configuration issue)
                return ErrorAction.CONTINUE
            else:
                return ErrorAction.CONTINUE
                
        except Exception as e:
            logger.error(f"Error in HTTP error handler: {e}")
            return ErrorAction.CONTINUE
    
    def handle_application_error(self, error: Exception, context: Dict[str, Any]) -> ErrorAction:
        """
        Handle application-level errors
        
        Args:
            error: The application error that occurred
            context: Context information
            
        Returns:
            ErrorAction to take
        """
        try:
            # Determine severity based on error type
            if isinstance(error, (MemoryError, SystemError)):
                severity = ErrorSeverity.CRITICAL
            elif isinstance(error, (ValueError, TypeError, KeyError)):
                severity = ErrorSeverity.HIGH
            else:
                severity = ErrorSeverity.MEDIUM
            
            error_info = self._create_error_info(
                error_type=ErrorType.APPLICATION_ERROR,
                severity=severity,
                message=str(error),
                context=context,
                exception=error
            )
            
            self._record_error(error_info)
            
            # Determine action based on severity
            if severity == ErrorSeverity.CRITICAL:
                return ErrorAction.EMERGENCY_STOP
            elif severity == ErrorSeverity.HIGH:
                return ErrorAction.STOP_WORKER
            else:
                return ErrorAction.CONTINUE
                
        except Exception as e:
            logger.error(f"Error in application error handler: {e}")
            return ErrorAction.CONTINUE
    
    def _handle_connection_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> ErrorAction:
        """Handle connection errors with circuit breaker"""
        endpoint = context.get('endpoint', 'unknown')
        
        # Get or create circuit breaker for endpoint
        if endpoint not in self.circuit_breakers:
            self.circuit_breakers[endpoint] = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60
            )
        
        circuit_breaker = self.circuit_breakers[endpoint]
        circuit_breaker._on_failure()
        
        if circuit_breaker.state == "open":
            logger.warning(f"Circuit breaker open for endpoint {endpoint}")
            return ErrorAction.THROTTLE
        
        return ErrorAction.RETRY
    
    def _handle_timeout_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> ErrorAction:
        """Handle timeout errors"""
        # Check if too many timeouts recently
        recent_timeouts = self._count_recent_errors(
            error_type=ErrorType.TIMEOUT_ERROR,
            minutes=1
        )
        
        if recent_timeouts > 10:
            logger.warning(f"Too many timeout errors: {recent_timeouts}")
            return ErrorAction.THROTTLE
        
        return ErrorAction.RETRY
    
    def _handle_server_error(self, error_info: ErrorInfo, context: Dict[str, Any]) -> ErrorAction:
        """Handle server errors (5xx)"""
        # Check error rate for this endpoint
        endpoint = context.get('endpoint', 'unknown')
        recent_errors = self._count_recent_endpoint_errors(endpoint, minutes=5)
        
        if recent_errors > 20:
            logger.warning(f"Too many server errors for endpoint {endpoint}: {recent_errors}")
            return ErrorAction.THROTTLE
        
        return ErrorAction.RETRY
    
    def _create_error_info(self, 
                          error_type: ErrorType,
                          severity: ErrorSeverity,
                          message: str,
                          context: Dict[str, Any],
                          exception: Optional[Exception] = None,
                          status_code: Optional[int] = None) -> ErrorInfo:
        """Create ErrorInfo object from error details"""
        
        stack_trace = None
        exception_type = None
        
        if exception:
            exception_type = type(exception).__name__
            stack_trace = traceback.format_exc()
        
        return ErrorInfo(
            error_type=error_type,
            severity=severity,
            message=message,
            timestamp=datetime.now(),
            endpoint=context.get('endpoint'),
            worker_id=context.get('worker_id'),
            status_code=status_code,
            response_time=context.get('response_time'),
            exception_type=exception_type,
            stack_trace=stack_trace
        )
    
    def _record_error(self, error_info: ErrorInfo):
        """Record error in history and notify callbacks"""
        try:
            # Add to history
            self.error_history.append(error_info)
            self.error_timestamps.append(error_info.timestamp)
            
            # Log error
            log_level = {
                ErrorSeverity.LOW: logging.INFO,
                ErrorSeverity.MEDIUM: logging.WARNING,
                ErrorSeverity.HIGH: logging.ERROR,
                ErrorSeverity.CRITICAL: logging.CRITICAL
            }.get(error_info.severity, logging.WARNING)
            
            logger.log(log_level, f"Error recorded: {error_info.message}")
            
            # Notify callbacks
            for callback in self.error_callbacks:
                try:
                    callback(error_info)
                except Exception as e:
                    logger.error(f"Error in error callback: {e}")
                    
        except Exception as e:
            logger.error(f"Error recording error: {e}")
    
    def _count_recent_errors(self, 
                           error_type: Optional[ErrorType] = None,
                           severity: Optional[ErrorSeverity] = None,
                           minutes: int = 1) -> int:
        """Count recent errors matching criteria"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            count = 0
            
            for error_info in self.error_history:
                if error_info.timestamp < cutoff_time:
                    continue
                
                if error_type and error_info.error_type != error_type:
                    continue
                
                if severity and error_info.severity != severity:
                    continue
                
                count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Error counting recent errors: {e}")
            return 0
    
    def _count_recent_endpoint_errors(self, endpoint: str, minutes: int = 1) -> int:
        """Count recent errors for specific endpoint"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=minutes)
            count = 0
            
            for error_info in self.error_history:
                if (error_info.timestamp >= cutoff_time and 
                    error_info.endpoint == endpoint):
                    count += 1
            
            return count
            
        except Exception as e:
            logger.error(f"Error counting endpoint errors: {e}")
            return 0
    
    def should_continue_test(self) -> bool:
        """
        Determine if load test should continue based on error rates
        
        Returns:
            True if test should continue, False if it should stop
        """
        try:
            # Check critical errors in last minute
            critical_errors = self._count_recent_errors(
                severity=ErrorSeverity.CRITICAL,
                minutes=1
            )
            
            if critical_errors >= self.critical_error_threshold:
                logger.error(f"Too many critical errors: {critical_errors}")
                return False
            
            # Check overall error rate in last minute
            total_errors_minute = self._count_recent_errors(minutes=1)
            if total_errors_minute >= self.max_errors_per_minute:
                logger.error(f"Error rate too high: {total_errors_minute}/minute")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking if test should continue: {e}")
            return True  # Default to continue on error
    
    def get_error_stats(self) -> ErrorStats:
        """Get current error statistics"""
        try:
            stats = ErrorStats()
            
            # Count errors by type and severity
            for error_info in self.error_history:
                stats.total_errors += 1
                stats.errors_by_type[error_info.error_type] += 1
                stats.errors_by_severity[error_info.severity] += 1
                
                if error_info.endpoint:
                    stats.errors_by_endpoint[error_info.endpoint] += 1
            
            # Count recent errors
            stats.errors_last_minute = self._count_recent_errors(minutes=1)
            stats.errors_last_hour = self._count_recent_errors(minutes=60)
            
            # Calculate error rate
            if stats.errors_last_minute > 0:
                stats.error_rate_per_minute = stats.errors_last_minute
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting error stats: {e}")
            return ErrorStats()
    
    def get_recent_errors(self, limit: int = 50) -> List[ErrorInfo]:
        """Get recent errors"""
        try:
            return list(self.error_history)[-limit:]
        except Exception as e:
            logger.error(f"Error getting recent errors: {e}")
            return []
    
    def add_error_callback(self, callback: Callable[[ErrorInfo], None]):
        """Add callback to be notified of errors"""
        self.error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable[[ErrorInfo], None]):
        """Remove error callback"""
        if callback in self.error_callbacks:
            self.error_callbacks.remove(callback)
    
    def reset_circuit_breaker(self, endpoint: str):
        """Manually reset circuit breaker for endpoint"""
        if endpoint in self.circuit_breakers:
            self.circuit_breakers[endpoint].failure_count = 0
            self.circuit_breakers[endpoint].state = "closed"
            logger.info(f"Reset circuit breaker for endpoint {endpoint}")
    
    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all circuit breakers"""
        return {
            endpoint: {
                "state": cb.state,
                "failure_count": cb.failure_count,
                "last_failure_time": cb.last_failure_time.isoformat() if cb.last_failure_time else None
            }
            for endpoint, cb in self.circuit_breakers.items()
        }
    
    def cleanup_old_errors(self, max_age_hours: int = 24):
        """Clean up old errors from history"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            # Remove old errors
            while (self.error_history and 
                   self.error_history[0].timestamp < cutoff_time):
                self.error_history.popleft()
            
            # Remove old timestamps
            while (self.error_timestamps and 
                   self.error_timestamps[0] < cutoff_time):
                self.error_timestamps.popleft()
            
            logger.debug(f"Cleaned up old errors, {len(self.error_history)} remaining")
            
        except Exception as e:
            logger.error(f"Error cleaning up old errors: {e}")

# Global error handler instance
error_handler = ErrorHandler()