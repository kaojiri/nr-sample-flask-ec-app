"""
Worker Pool Implementation for Load Testing Automation
"""
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4

from http_client import AsyncHTTPClient, RequestResult
from endpoint_selector import endpoint_selector, EndpointConfig
from error_handler import error_handler, ErrorAction
from resource_monitor import resource_monitor, LoadAdjustmentAction

logger = logging.getLogger(__name__)

class WorkerStatus(Enum):
    """Status of individual worker"""
    IDLE = "idle"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

class PoolStatus(Enum):
    """Status of worker pool"""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class WorkerConfig:
    """Configuration for worker behavior"""
    request_interval_min: float = 1.0
    request_interval_max: float = 5.0
    max_errors_per_minute: int = 100
    timeout: int = 30
    enable_logging: bool = True
    enable_user_login: bool = False

@dataclass
class WorkerStats:
    """Statistics for individual worker"""
    worker_id: str
    status: WorkerStatus = WorkerStatus.IDLE
    requests_sent: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    errors_last_minute: int = 0
    last_request_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.requests_sent == 0:
            return 0.0
        return (self.successful_requests / self.requests_sent) * 100
    
    @property
    def average_response_time(self) -> float:
        """Calculate average response time"""
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time / self.successful_requests

class LoadTestWorker:
    """
    Individual worker that sends HTTP requests to selected endpoints
    """
    
    def __init__(self, worker_id: str, config: WorkerConfig):
        self.worker_id = worker_id
        self.config = config
        self.stats = WorkerStats(worker_id=worker_id)
        self._task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._http_client: Optional[AsyncHTTPClient] = None
        self._error_timestamps: List[datetime] = []
        
    async def start(self):
        """Start the worker"""
        try:
            if self._task and not self._task.done():
                logger.warning(f"Worker {self.worker_id} is already running")
                return
            
            self.stats.status = WorkerStatus.RUNNING
            self.stats.start_time = datetime.now()
            self._stop_event.clear()
            
            # Create HTTP client
            self._http_client = AsyncHTTPClient(
                default_timeout=self.config.timeout,
                max_connections=10,  # Per worker limit
                max_connections_per_host=5
            )
            
            # Start worker task
            self._task = asyncio.create_task(self._worker_loop())
            logger.info(f"Worker {self.worker_id} started")
            
        except Exception as e:
            self.stats.status = WorkerStatus.ERROR
            logger.error(f"Error starting worker {self.worker_id}: {e}")
            raise
    
    async def stop(self, timeout: float = 10.0):
        """Stop the worker gracefully"""
        try:
            if not self._task or self._task.done():
                self.stats.status = WorkerStatus.STOPPED
                return
            
            self.stats.status = WorkerStatus.STOPPING
            self._stop_event.set()
            
            # Wait for worker to stop gracefully
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Worker {self.worker_id} did not stop gracefully, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            
            # Close HTTP client
            if self._http_client:
                await self._http_client.close()
                self._http_client = None
            
            self.stats.status = WorkerStatus.STOPPED
            logger.info(f"Worker {self.worker_id} stopped")
            
        except Exception as e:
            self.stats.status = WorkerStatus.ERROR
            logger.error(f"Error stopping worker {self.worker_id}: {e}")
    
    async def _worker_loop(self):
        """Main worker loop that sends requests"""
        try:
            async with self._http_client:
                while not self._stop_event.is_set():
                    try:
                        # Check error rate before making request
                        if self._should_throttle():
                            await asyncio.sleep(1.0)
                            continue
                        
                        # Select endpoint
                        endpoint = endpoint_selector.select_endpoint()
                        if not endpoint:
                            logger.warning(f"Worker {self.worker_id}: No endpoints available")
                            await asyncio.sleep(5.0)
                            continue
                        
                        # Make request
                        await self._make_request(endpoint)
                        
                        # Wait random interval before next request
                        interval = random.uniform(
                            self.config.request_interval_min,
                            self.config.request_interval_max
                        )
                        
                        # Use wait_for to allow interruption during sleep
                        try:
                            await asyncio.wait_for(
                                self._stop_event.wait(),
                                timeout=interval
                            )
                            # If we get here, stop was requested
                            break
                        except asyncio.TimeoutError:
                            # Normal case - continue with next request
                            continue
                            
                    except asyncio.CancelledError:
                        logger.info(f"Worker {self.worker_id} cancelled")
                        break
                    except Exception as e:
                        logger.error(f"Worker {self.worker_id} loop error: {e}")
                        await asyncio.sleep(1.0)
                        
        except Exception as e:
            self.stats.status = WorkerStatus.ERROR
            logger.error(f"Worker {self.worker_id} fatal error: {e}")
        finally:
            logger.debug(f"Worker {self.worker_id} loop ended")
    
    async def _make_request(self, endpoint: EndpointConfig):
        """Make HTTP request to endpoint and update statistics"""
        try:
            # Check if we should continue based on error rates
            if not error_handler.should_continue_test():
                logger.warning(f"Worker {self.worker_id}: Stopping due to high error rate")
                self._stop_event.set()
                return
            
            # Prepare request headers
            headers = {}
            
            # Add user session cookie if user login is enabled
            if self.config.enable_user_login:
                session = self._get_random_user_session()
                if session:
                    headers['Cookie'] = f"session={session.session_cookie}"
                    logger.debug(f"Worker {self.worker_id}: Using session for user {session.username}")
                else:
                    logger.warning(f"Worker {self.worker_id}: No user session available, making request without authentication")
            
            # Make the request
            result = await self._http_client.make_request(
                url=endpoint.url,
                method=endpoint.method,
                timeout=self.config.timeout,
                headers=headers,
                worker_id=self.worker_id
            )
            
            # Update worker statistics
            self.stats.requests_sent += 1
            self.stats.last_request_time = datetime.now()
            
            if result.is_success:
                self.stats.successful_requests += 1
                self.stats.total_response_time += result.response_time
            else:
                self.stats.failed_requests += 1
                self.stats.last_error_time = datetime.now()
                self._record_error()
            
            # Update endpoint statistics
            endpoint_selector.update_endpoint_stats(
                endpoint.name,
                result.is_success,
                result.response_time
            )
            
            # Record statistics for real-time monitoring
            if hasattr(self, '_statistics_callback') and self._statistics_callback:
                try:
                    self._statistics_callback(
                        endpoint=endpoint.name,
                        method=endpoint.method,
                        status_code=result.status_code,
                        response_time=result.response_time,
                        success=result.is_success,
                        error_message=result.error_message
                    )
                except Exception as e:
                    logger.error(f"Error recording statistics: {e}")
            
            # Log request if enabled
            if self.config.enable_logging:
                from http_client import request_logger
                request_logger.log_request(result)
            
            logger.debug(
                f"Worker {self.worker_id}: {endpoint.name} - "
                f"{result.status_code} - {result.response_time:.3f}s"
            )
            
        except Exception as e:
            self.stats.failed_requests += 1
            self.stats.last_error_time = datetime.now()
            self._record_error()
            
            # Record failed request in statistics
            if hasattr(self, '_statistics_callback') and self._statistics_callback:
                try:
                    self._statistics_callback(
                        endpoint=endpoint.name,
                        method=endpoint.method,
                        status_code=None,
                        response_time=0.0,
                        success=False,
                        error_message=str(e)
                    )
                except Exception as callback_error:
                    logger.error(f"Error recording failed request statistics: {callback_error}")
            
            logger.error(f"Worker {self.worker_id} request error: {e}")
    
    def _record_error(self):
        """Record error timestamp for rate limiting"""
        now = datetime.now()
        self._error_timestamps.append(now)
        
        # Clean old error timestamps (older than 1 minute)
        cutoff = now - timedelta(minutes=1)
        self._error_timestamps = [
            ts for ts in self._error_timestamps if ts > cutoff
        ]
        
        self.stats.errors_last_minute = len(self._error_timestamps)
    
    def _should_throttle(self) -> bool:
        """Check if worker should throttle due to high error rate"""
        return self.stats.errors_last_minute >= self.config.max_errors_per_minute
    
    def get_stats(self) -> WorkerStats:
        """Get current worker statistics"""
        return self.stats
    
    def set_statistics_callback(self, callback: Optional[Callable]):
        """Set callback for recording statistics"""
        self._statistics_callback = callback
    
    def _get_random_user_session(self):
        """Get a random user session for authenticated requests"""
        try:
            from user_session_manager import get_user_session_manager
            manager = get_user_session_manager()
            return manager.get_random_session()
        except Exception as e:
            logger.error(f"Error getting user session: {e}")
            return None

class WorkerPool:
    """
    Manages a pool of workers for load testing with dynamic scaling
    """
    
    def __init__(self, max_workers: int = 50):
        self.max_workers = max_workers
        self.workers: Dict[str, LoadTestWorker] = {}
        self.status = PoolStatus.IDLE
        self._target_worker_count = 0
        self._config: Optional[WorkerConfig] = None
        self._management_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        
        # Load adjustment state
        self._is_throttled = False
        self._throttle_factor = 1.0  # 1.0 = normal, 0.5 = half speed, etc.
        self._original_target_count = 0
        
        # Register for load adjustment callbacks
        resource_monitor.add_load_adjustment_callback(self._handle_load_adjustment)
        
    async def start_workers(self, worker_count: int, config: WorkerConfig):
        """
        Start specified number of workers with given configuration
        
        Args:
            worker_count: Number of workers to start
            config: Configuration for worker behavior
        """
        try:
            if self.status == PoolStatus.RUNNING:
                logger.warning("Worker pool is already running")
                return
            
            if worker_count > self.max_workers:
                raise ValueError(f"Worker count {worker_count} exceeds maximum {self.max_workers}")
            
            self.status = PoolStatus.STARTING
            self._target_worker_count = worker_count
            self._config = config
            self._stop_event.clear()
            
            logger.info(f"Starting worker pool with {worker_count} workers")
            
            # Start management task
            self._management_task = asyncio.create_task(self._management_loop())
            
            # Wait for workers to start
            await self._scale_to_target()
            
            self.status = PoolStatus.RUNNING
            logger.info(f"Worker pool started with {len(self.workers)} workers")
            
        except Exception as e:
            self.status = PoolStatus.ERROR
            logger.error(f"Error starting worker pool: {e}")
            raise
    
    async def stop_workers(self, timeout: float = 30.0):
        """Stop all workers gracefully"""
        try:
            if self.status in [PoolStatus.STOPPED, PoolStatus.IDLE]:
                return
            
            self.status = PoolStatus.STOPPING
            self._stop_event.set()
            
            logger.info(f"Stopping worker pool with {len(self.workers)} workers")
            
            # Stop management task
            if self._management_task and not self._management_task.done():
                self._management_task.cancel()
                try:
                    await self._management_task
                except asyncio.CancelledError:
                    pass
            
            # Stop all workers
            stop_tasks = []
            for worker in self.workers.values():
                stop_tasks.append(worker.stop(timeout=timeout/len(self.workers) if self.workers else timeout))
            
            if stop_tasks:
                await asyncio.gather(*stop_tasks, return_exceptions=True)
            
            self.workers.clear()
            self.status = PoolStatus.STOPPED
            logger.info("Worker pool stopped")
            
        except Exception as e:
            self.status = PoolStatus.ERROR
            logger.error(f"Error stopping worker pool: {e}")
    
    async def adjust_worker_count(self, new_count: int):
        """
        Dynamically adjust the number of workers
        
        Args:
            new_count: New target number of workers
        """
        try:
            if new_count > self.max_workers:
                raise ValueError(f"Worker count {new_count} exceeds maximum {self.max_workers}")
            
            if new_count < 0:
                raise ValueError("Worker count cannot be negative")
            
            old_count = self._target_worker_count
            self._target_worker_count = new_count
            
            logger.info(f"Adjusting worker count from {old_count} to {new_count}")
            
            # The management loop will handle the actual scaling
            
        except Exception as e:
            logger.error(f"Error adjusting worker count: {e}")
            raise
    
    async def _management_loop(self):
        """Management loop that handles worker lifecycle"""
        try:
            while not self._stop_event.is_set():
                try:
                    # Scale workers to target count
                    await self._scale_to_target()
                    
                    # Check worker health and restart failed workers
                    await self._check_worker_health()
                    
                    # Wait before next management cycle
                    try:
                        await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                        break  # Stop requested
                    except asyncio.TimeoutError:
                        continue  # Normal management cycle
                        
                except Exception as e:
                    logger.error(f"Error in worker management loop: {e}")
                    await asyncio.sleep(1.0)
                    
        except asyncio.CancelledError:
            logger.info("Worker management loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in worker management loop: {e}")
    
    async def _scale_to_target(self):
        """Scale workers to target count"""
        try:
            current_count = len(self.workers)
            target_count = self._target_worker_count
            
            if current_count < target_count:
                # Need to start more workers
                workers_to_start = target_count - current_count
                start_tasks = []
                
                for _ in range(workers_to_start):
                    worker_id = f"worker-{uuid4().hex[:8]}"
                    worker = LoadTestWorker(worker_id, self._config)
                    self.workers[worker_id] = worker
                    start_tasks.append(worker.start())
                
                if start_tasks:
                    await asyncio.gather(*start_tasks, return_exceptions=True)
                    logger.info(f"Started {workers_to_start} new workers")
            
            elif current_count > target_count:
                # Need to stop some workers
                workers_to_stop = current_count - target_count
                workers_list = list(self.workers.items())
                stop_tasks = []
                
                for i in range(workers_to_stop):
                    worker_id, worker = workers_list[i]
                    stop_tasks.append(worker.stop())
                    del self.workers[worker_id]
                
                if stop_tasks:
                    await asyncio.gather(*stop_tasks, return_exceptions=True)
                    logger.info(f"Stopped {workers_to_stop} workers")
                    
        except Exception as e:
            logger.error(f"Error scaling workers: {e}")
    
    async def _check_worker_health(self):
        """Check worker health and restart failed workers"""
        try:
            failed_workers = []
            
            for worker_id, worker in self.workers.items():
                if worker.stats.status == WorkerStatus.ERROR:
                    failed_workers.append(worker_id)
            
            # Restart failed workers
            for worker_id in failed_workers:
                try:
                    old_worker = self.workers[worker_id]
                    await old_worker.stop()
                    
                    # Create new worker with same ID
                    new_worker = LoadTestWorker(worker_id, self._config)
                    self.workers[worker_id] = new_worker
                    await new_worker.start()
                    
                    logger.info(f"Restarted failed worker {worker_id}")
                    
                except Exception as e:
                    logger.error(f"Error restarting worker {worker_id}: {e}")
                    # Remove failed worker from pool
                    if worker_id in self.workers:
                        del self.workers[worker_id]
                        
        except Exception as e:
            logger.error(f"Error checking worker health: {e}")
    
    def get_worker_status(self) -> List[Dict[str, Any]]:
        """Get status of all workers"""
        return [
            {
                "worker_id": worker.worker_id,
                "status": worker.stats.status.value,
                "requests_sent": worker.stats.requests_sent,
                "successful_requests": worker.stats.successful_requests,
                "failed_requests": worker.stats.failed_requests,
                "success_rate": worker.stats.success_rate,
                "average_response_time": worker.stats.average_response_time,
                "errors_last_minute": worker.stats.errors_last_minute,
                "last_request_time": worker.stats.last_request_time.isoformat() if worker.stats.last_request_time else None,
                "start_time": worker.stats.start_time.isoformat() if worker.stats.start_time else None
            }
            for worker in self.workers.values()
        ]
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get overall pool statistics"""
        if not self.workers:
            return {
                "status": self.status.value,
                "worker_count": 0,
                "target_worker_count": self._target_worker_count,
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "success_rate": 0.0,
                "average_response_time": 0.0
            }
        
        # Aggregate statistics from all workers
        total_requests = sum(w.stats.requests_sent for w in self.workers.values())
        successful_requests = sum(w.stats.successful_requests for w in self.workers.values())
        failed_requests = sum(w.stats.failed_requests for w in self.workers.values())
        total_response_time = sum(w.stats.total_response_time for w in self.workers.values())
        
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0.0
        avg_response_time = (total_response_time / successful_requests) if successful_requests > 0 else 0.0
        
        return {
            "status": self.status.value,
            "worker_count": len(self.workers),
            "target_worker_count": self._target_worker_count,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
            "average_response_time": avg_response_time,
            "workers": self.get_worker_status()
        }
    
    async def pause_workers(self):
        """Pause all workers temporarily"""
        try:
            if self.status != PoolStatus.RUNNING:
                logger.warning(f"Cannot pause workers - pool status is {self.status}")
                return
            
            logger.info("Pausing worker pool")
            
            # Pause all workers by stopping their tasks but keeping the workers
            pause_tasks = []
            for worker in self.workers.values():
                if worker._task and not worker._task.done():
                    worker.stats.status = WorkerStatus.STOPPING
                    worker._stop_event.set()
                    pause_tasks.append(worker._task)
            
            # Wait for workers to pause
            if pause_tasks:
                await asyncio.gather(*pause_tasks, return_exceptions=True)
            
            # Update worker status to idle
            for worker in self.workers.values():
                worker.stats.status = WorkerStatus.IDLE
                worker._stop_event.clear()
            
            logger.info(f"Paused {len(self.workers)} workers")
            
        except Exception as e:
            logger.error(f"Error pausing workers: {e}")
    
    async def resume_workers(self):
        """Resume paused workers"""
        try:
            if self.status != PoolStatus.RUNNING:
                logger.warning(f"Cannot resume workers - pool status is {self.status}")
                return
            
            logger.info("Resuming worker pool")
            
            # Resume all workers by restarting their tasks
            resume_tasks = []
            for worker in self.workers.values():
                if worker.stats.status == WorkerStatus.IDLE:
                    resume_tasks.append(worker.start())
            
            # Wait for workers to resume
            if resume_tasks:
                await asyncio.gather(*resume_tasks, return_exceptions=True)
            
            logger.info(f"Resumed {len(self.workers)} workers")
            
        except Exception as e:
            logger.error(f"Error resuming workers: {e}")
    
    async def emergency_stop(self):
        """Emergency stop all workers immediately"""
        try:
            logger.warning("Emergency stop requested for worker pool")
            self.status = PoolStatus.STOPPING
            self._stop_event.set()
            
            # Cancel all worker tasks immediately
            cancel_tasks = []
            for worker in self.workers.values():
                if worker._task and not worker._task.done():
                    worker._task.cancel()
                    cancel_tasks.append(worker._task)
            
            # Wait for cancellations with short timeout
            if cancel_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*cancel_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("Some workers did not stop during emergency stop")
            
            # Close HTTP clients
            for worker in self.workers.values():
                if worker._http_client:
                    try:
                        await worker._http_client.close()
                    except Exception as e:
                        logger.error(f"Error closing HTTP client during emergency stop: {e}")
            
            self.workers.clear()
            self.status = PoolStatus.STOPPED
            logger.info("Emergency stop completed")
            
        except Exception as e:
            self.status = PoolStatus.ERROR
            logger.error(f"Error during emergency stop: {e}")
    
    def set_statistics_callback(self, callback: Optional[Callable]):
        """Set statistics callback for all workers"""
        try:
            for worker in self.workers.values():
                worker.set_statistics_callback(callback)
            logger.debug(f"Set statistics callback for {len(self.workers)} workers")
        except Exception as e:
            logger.error(f"Error setting statistics callback: {e}")
    
    def _handle_load_adjustment(self, action: LoadAdjustmentAction, context: Dict[str, Any]):
        """Handle load adjustment requests from resource monitor"""
        try:
            logger.info(f"Handling load adjustment: {action.value}")
            
            if action == LoadAdjustmentAction.EMERGENCY_STOP:
                # Emergency stop - trigger immediate shutdown
                asyncio.create_task(self.emergency_stop())
                
            elif action == LoadAdjustmentAction.PAUSE_TEST:
                # Pause test - stop all workers temporarily
                asyncio.create_task(self.stop_workers())
                
            elif action == LoadAdjustmentAction.REDUCE_WORKERS:
                # Reduce worker count by 25%
                if not self._original_target_count:
                    self._original_target_count = self._target_worker_count
                
                new_count = max(1, int(self._target_worker_count * 0.75))
                asyncio.create_task(self.adjust_worker_count(new_count))
                logger.info(f"Reduced worker count to {new_count} due to resource pressure")
                
            elif action == LoadAdjustmentAction.THROTTLE_REQUESTS:
                # Throttle request rate
                self._is_throttled = True
                self._throttle_factor = max(0.1, self._throttle_factor * 0.8)  # Reduce by 20%
                logger.info(f"Throttling requests by factor {self._throttle_factor}")
                
                # Update worker configurations
                if self._config:
                    # Increase request intervals to throttle
                    original_min = self._config.request_interval_min
                    original_max = self._config.request_interval_max
                    
                    self._config.request_interval_min = original_min / self._throttle_factor
                    self._config.request_interval_max = original_max / self._throttle_factor
                    
        except Exception as e:
            logger.error(f"Error handling load adjustment: {e}")
    
    def reset_load_adjustments(self):
        """Reset load adjustments to normal operation"""
        try:
            if self._is_throttled:
                self._is_throttled = False
                self._throttle_factor = 1.0
                logger.info("Reset request throttling")
            
            if self._original_target_count and self._original_target_count != self._target_worker_count:
                asyncio.create_task(self.adjust_worker_count(self._original_target_count))
                logger.info(f"Reset worker count to {self._original_target_count}")
                self._original_target_count = 0
                
        except Exception as e:
            logger.error(f"Error resetting load adjustments: {e}")
    
    def get_load_adjustment_status(self) -> Dict[str, Any]:
        """Get current load adjustment status"""
        return {
            "is_throttled": self._is_throttled,
            "throttle_factor": self._throttle_factor,
            "original_target_count": self._original_target_count,
            "current_target_count": self._target_worker_count
        }

# Global worker pool instance
worker_pool = WorkerPool()