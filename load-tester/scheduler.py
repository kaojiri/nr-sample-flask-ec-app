"""
Load Test Scheduler - Handles scheduled and recurring load test execution
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum
from uuid import uuid4
from pathlib import Path
import croniter

logger = logging.getLogger(__name__)

class ScheduleType(Enum):
    """Type of schedule"""
    ONE_TIME = "one_time"
    RECURRING = "recurring"
    CRON = "cron"

class ScheduleStatus(Enum):
    """Status of scheduled task"""
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"

@dataclass
class ScheduleConfig:
    """Configuration for scheduled load test"""
    name: str
    schedule_type: ScheduleType
    load_test_config: Dict[str, Any]  # LoadTestConfig as dict
    
    # One-time schedule
    start_time: Optional[datetime] = None
    
    # Recurring schedule
    interval_minutes: Optional[int] = None
    max_executions: Optional[int] = None
    
    # Cron schedule
    cron_expression: Optional[str] = None
    
    # Common options
    enabled: bool = True
    timezone: str = "UTC"
    
    def validate(self) -> List[str]:
        """Validate schedule configuration"""
        errors = []
        
        if not self.name or not self.name.strip():
            errors.append("Schedule name is required")
        
        if self.schedule_type == ScheduleType.ONE_TIME:
            if not self.start_time:
                errors.append("Start time is required for one-time schedule")
            elif self.start_time <= datetime.now():
                errors.append("Start time must be in the future")
        
        elif self.schedule_type == ScheduleType.RECURRING:
            if not self.interval_minutes or self.interval_minutes < 1:
                errors.append("Interval minutes must be at least 1 for recurring schedule")
            if self.max_executions and self.max_executions < 1:
                errors.append("Max executions must be at least 1 if specified")
        
        elif self.schedule_type == ScheduleType.CRON:
            if not self.cron_expression:
                errors.append("Cron expression is required for cron schedule")
            else:
                try:
                    croniter.croniter(self.cron_expression)
                except Exception as e:
                    errors.append(f"Invalid cron expression: {e}")
        
        return errors

@dataclass
class ScheduledTask:
    """Scheduled load test task"""
    id: str
    config: ScheduleConfig
    status: ScheduleStatus = ScheduleStatus.PENDING
    created_time: datetime = None
    last_execution: Optional[datetime] = None
    next_execution: Optional[datetime] = None
    execution_count: int = 0
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = datetime.now()
        if self.next_execution is None:
            self.next_execution = self._calculate_next_execution()
    
    def _calculate_next_execution(self) -> Optional[datetime]:
        """Calculate next execution time based on schedule type"""
        now = datetime.now()
        
        if self.config.schedule_type == ScheduleType.ONE_TIME:
            if self.execution_count == 0 and self.config.start_time:
                return self.config.start_time
            return None
        
        elif self.config.schedule_type == ScheduleType.RECURRING:
            if self.config.max_executions and self.execution_count >= self.config.max_executions:
                return None
            
            if self.last_execution:
                return self.last_execution + timedelta(minutes=self.config.interval_minutes)
            else:
                return now + timedelta(minutes=self.config.interval_minutes)
        
        elif self.config.schedule_type == ScheduleType.CRON:
            try:
                cron = croniter.croniter(self.config.cron_expression, now)
                return cron.get_next(datetime)
            except Exception as e:
                logger.error(f"Error calculating next cron execution: {e}")
                return None
        
        return None
    
    def update_next_execution(self):
        """Update next execution time after execution"""
        self.next_execution = self._calculate_next_execution()
    
    @property
    def is_due(self) -> bool:
        """Check if task is due for execution"""
        if not self.next_execution or self.status != ScheduleStatus.ACTIVE:
            return False
        return datetime.now() >= self.next_execution
    
    @property
    def is_active(self) -> bool:
        """Check if task is active and can be executed"""
        return self.status == ScheduleStatus.ACTIVE and self.config.enabled
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        
        # Convert datetime objects to ISO strings
        if self.created_time:
            data['created_time'] = self.created_time.isoformat()
        if self.last_execution:
            data['last_execution'] = self.last_execution.isoformat()
        if self.next_execution:
            data['next_execution'] = self.next_execution.isoformat()
        
        # Convert enums to strings
        data['status'] = self.status.value
        data['config']['schedule_type'] = self.config.schedule_type.value
        
        # Convert start_time in config
        if self.config.start_time:
            data['config']['start_time'] = self.config.start_time.isoformat()
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ScheduledTask':
        """Create from dictionary"""
        # Convert ISO strings back to datetime objects
        if data.get('created_time'):
            data['created_time'] = datetime.fromisoformat(data['created_time'])
        if data.get('last_execution'):
            data['last_execution'] = datetime.fromisoformat(data['last_execution'])
        if data.get('next_execution'):
            data['next_execution'] = datetime.fromisoformat(data['next_execution'])
        
        # Convert strings back to enums
        if 'status' in data:
            data['status'] = ScheduleStatus(data['status'])
        
        # Reconstruct ScheduleConfig
        if 'config' in data:
            config_data = data['config']
            config_data['schedule_type'] = ScheduleType(config_data['schedule_type'])
            if config_data.get('start_time'):
                config_data['start_time'] = datetime.fromisoformat(config_data['start_time'])
            data['config'] = ScheduleConfig(**config_data)
        
        return cls(**data)

class SchedulePersistence:
    """Handles persistence of scheduled tasks"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.schedules_file = self.data_dir / "schedules.json"
    
    def save_schedule(self, task: ScheduledTask):
        """Save a scheduled task"""
        try:
            schedules = self.load_all_schedules()
            schedules[task.id] = task.to_dict()
            
            with open(self.schedules_file, 'w') as f:
                json.dump(schedules, f, indent=2, default=str)
                
        except Exception as e:
            logger.error(f"Error saving schedule {task.id}: {e}")
            raise
    
    def load_all_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Load all scheduled tasks from disk"""
        try:
            if not self.schedules_file.exists():
                return {}
            
            with open(self.schedules_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
            return {}
    
    def delete_schedule(self, task_id: str):
        """Delete a scheduled task"""
        try:
            schedules = self.load_all_schedules()
            if task_id in schedules:
                del schedules[task_id]
                
                with open(self.schedules_file, 'w') as f:
                    json.dump(schedules, f, indent=2, default=str)
                    
        except Exception as e:
            logger.error(f"Error deleting schedule {task_id}: {e}")
            raise

class LoadTestScheduler:
    """Main scheduler for load test automation"""
    
    def __init__(self, load_test_manager_factory: Callable = None):
        self.persistence = SchedulePersistence()
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        self.load_test_manager_factory = load_test_manager_factory
        
        # Load existing schedules
        self._load_schedules()
    
    def _load_schedules(self):
        """Load scheduled tasks from persistence"""
        try:
            schedules_data = self.persistence.load_all_schedules()
            for task_id, task_data in schedules_data.items():
                task = ScheduledTask.from_dict(task_data)
                self.scheduled_tasks[task_id] = task
                
            logger.info(f"Loaded {len(self.scheduled_tasks)} scheduled tasks")
            
        except Exception as e:
            logger.error(f"Error loading schedules: {e}")
    
    def create_schedule(self, config: ScheduleConfig) -> ScheduledTask:
        """Create a new scheduled task"""
        # Validate configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid schedule configuration: {', '.join(errors)}")
        
        # Create task
        task = ScheduledTask(
            id=str(uuid4()),
            config=config,
            status=ScheduleStatus.ACTIVE if config.enabled else ScheduleStatus.PAUSED
        )
        
        # Save to persistence and memory
        self.scheduled_tasks[task.id] = task
        self.persistence.save_schedule(task)
        
        logger.info(f"Created scheduled task {task.id}: {config.name}")
        return task
    
    def get_schedule(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a scheduled task by ID"""
        return self.scheduled_tasks.get(task_id)
    
    def get_all_schedules(self) -> List[ScheduledTask]:
        """Get all scheduled tasks"""
        return list(self.scheduled_tasks.values())
    
    def get_active_schedules(self) -> List[ScheduledTask]:
        """Get all active scheduled tasks"""
        return [task for task in self.scheduled_tasks.values() if task.is_active]
    
    def update_schedule(self, task_id: str, config: ScheduleConfig) -> bool:
        """Update a scheduled task configuration"""
        task = self.scheduled_tasks.get(task_id)
        if not task:
            return False
        
        # Validate new configuration
        errors = config.validate()
        if errors:
            raise ValueError(f"Invalid schedule configuration: {', '.join(errors)}")
        
        # Update task
        task.config = config
        task.update_next_execution()
        
        # Update status based on enabled flag
        if config.enabled and task.status == ScheduleStatus.PAUSED:
            task.status = ScheduleStatus.ACTIVE
        elif not config.enabled and task.status == ScheduleStatus.ACTIVE:
            task.status = ScheduleStatus.PAUSED
        
        # Save changes
        self.persistence.save_schedule(task)
        
        logger.info(f"Updated scheduled task {task_id}")
        return True
    
    def delete_schedule(self, task_id: str) -> bool:
        """Delete a scheduled task"""
        if task_id not in self.scheduled_tasks:
            return False
        
        # Remove from memory and persistence
        del self.scheduled_tasks[task_id]
        self.persistence.delete_schedule(task_id)
        
        logger.info(f"Deleted scheduled task {task_id}")
        return True
    
    def enable_schedule(self, task_id: str) -> bool:
        """Enable a scheduled task"""
        task = self.scheduled_tasks.get(task_id)
        if not task:
            return False
        
        task.config.enabled = True
        task.status = ScheduleStatus.ACTIVE
        task.update_next_execution()
        
        self.persistence.save_schedule(task)
        logger.info(f"Enabled scheduled task {task_id}")
        return True
    
    def disable_schedule(self, task_id: str) -> bool:
        """Disable a scheduled task"""
        task = self.scheduled_tasks.get(task_id)
        if not task:
            return False
        
        task.config.enabled = False
        task.status = ScheduleStatus.PAUSED
        
        self.persistence.save_schedule(task)
        logger.info(f"Disabled scheduled task {task_id}")
        return True
    
    async def start_scheduler(self):
        """Start the scheduler loop"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Load test scheduler started")
    
    async def stop_scheduler(self):
        """Stop the scheduler loop"""
        if not self.running:
            return
        
        self.running = False
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Load test scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        logger.info("Scheduler loop started")
        
        while self.running:
            try:
                await self._check_and_execute_tasks()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _check_and_execute_tasks(self):
        """Check for due tasks and execute them"""
        now = datetime.now()
        
        for task in list(self.scheduled_tasks.values()):
            try:
                if task.is_due:
                    await self._execute_scheduled_task(task)
                    
                # Clean up completed one-time tasks
                elif (task.config.schedule_type == ScheduleType.ONE_TIME and 
                      task.status == ScheduleStatus.COMPLETED and
                      task.last_execution and 
                      (now - task.last_execution).days > 1):
                    
                    logger.info(f"Cleaning up completed one-time task {task.id}")
                    self.delete_schedule(task.id)
                    
            except Exception as e:
                logger.error(f"Error processing scheduled task {task.id}: {e}")
                task.status = ScheduleStatus.FAILED
                task.error_message = str(e)
                self.persistence.save_schedule(task)
    
    async def _execute_scheduled_task(self, task: ScheduledTask):
        """Execute a scheduled load test task"""
        logger.info(f"Executing scheduled task {task.id}: {task.config.name}")
        
        try:
            # Get load test manager
            if not self.load_test_manager_factory:
                raise RuntimeError("Load test manager factory not configured")
            
            load_test_manager = self.load_test_manager_factory()
            if not load_test_manager:
                raise RuntimeError("Load test manager not available")
            
            # Create load test config from stored data
            from load_test_manager import LoadTestConfig
            config_data = task.config.load_test_config.copy()
            
            # Add schedule info to session name
            config_data['session_name'] = f"{task.config.name}_scheduled_{task.execution_count + 1}"
            
            load_test_config = LoadTestConfig(**config_data)
            
            # Start the load test
            session = await load_test_manager.start_test(load_test_config)
            
            # Update task execution info
            task.last_execution = datetime.now()
            task.execution_count += 1
            task.update_next_execution()
            
            # Update status based on schedule type
            if task.config.schedule_type == ScheduleType.ONE_TIME:
                task.status = ScheduleStatus.COMPLETED
            elif (task.config.schedule_type == ScheduleType.RECURRING and 
                  task.config.max_executions and 
                  task.execution_count >= task.config.max_executions):
                task.status = ScheduleStatus.COMPLETED
            
            # Save changes
            self.persistence.save_schedule(task)
            
            logger.info(f"Successfully started scheduled load test {session.id} for task {task.id}")
            
        except Exception as e:
            logger.error(f"Failed to execute scheduled task {task.id}: {e}")
            task.status = ScheduleStatus.FAILED
            task.error_message = str(e)
            self.persistence.save_schedule(task)
            raise
    
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Get current scheduler status"""
        active_tasks = self.get_active_schedules()
        
        return {
            "running": self.running,
            "total_schedules": len(self.scheduled_tasks),
            "active_schedules": len(active_tasks),
            "next_execution": min([task.next_execution for task in active_tasks 
                                 if task.next_execution], default=None),
            "schedules_by_status": {
                status.value: len([t for t in self.scheduled_tasks.values() if t.status == status])
                for status in ScheduleStatus
            }
        }

# Global scheduler instance
scheduler: Optional[LoadTestScheduler] = None

def get_scheduler() -> Optional[LoadTestScheduler]:
    """Get the global scheduler instance"""
    return scheduler

def initialize_scheduler(load_test_manager_factory: Callable = None):
    """Initialize the global scheduler"""
    global scheduler
    if scheduler is None:
        scheduler = LoadTestScheduler(load_test_manager_factory)
    return scheduler