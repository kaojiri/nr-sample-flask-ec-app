"""
Test scheduling functionality
"""
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock

# Mock the dependencies
import sys
from unittest.mock import MagicMock
sys.modules['croniter'] = MagicMock()

from scheduler import (
    ScheduleConfig, ScheduledTask, ScheduleType, ScheduleStatus,
    LoadTestScheduler
)

def test_schedule_config_validation():
    """Test schedule configuration validation"""
    
    # Valid one-time schedule
    config = ScheduleConfig(
        name="Test Schedule",
        schedule_type=ScheduleType.ONE_TIME,
        load_test_config={"concurrent_users": 10},
        start_time=datetime.now() + timedelta(hours=1)
    )
    errors = config.validate()
    assert len(errors) == 0
    
    # Invalid - no name
    config = ScheduleConfig(
        name="",
        schedule_type=ScheduleType.ONE_TIME,
        load_test_config={"concurrent_users": 10}
    )
    errors = config.validate()
    assert "Schedule name is required" in errors
    
    # Invalid - past start time
    config = ScheduleConfig(
        name="Test Schedule",
        schedule_type=ScheduleType.ONE_TIME,
        load_test_config={"concurrent_users": 10},
        start_time=datetime.now() - timedelta(hours=1)
    )
    errors = config.validate()
    assert "Start time must be in the future" in errors

def test_scheduled_task_creation():
    """Test scheduled task creation and properties"""
    
    config = ScheduleConfig(
        name="Test Schedule",
        schedule_type=ScheduleType.RECURRING,
        load_test_config={"concurrent_users": 10},
        interval_minutes=60
    )
    
    task = ScheduledTask(
        id="test-123",
        config=config,
        status=ScheduleStatus.ACTIVE
    )
    
    assert task.id == "test-123"
    assert task.config.name == "Test Schedule"
    assert task.status == ScheduleStatus.ACTIVE
    assert task.is_active == True
    assert task.execution_count == 0

def test_scheduler_creation():
    """Test scheduler creation and basic operations"""
    
    scheduler = LoadTestScheduler()
    
    # Test initial state
    assert len(scheduler.get_all_schedules()) == 0
    assert len(scheduler.get_active_schedules()) == 0
    
    # Test creating a schedule
    config = ScheduleConfig(
        name="Test Schedule",
        schedule_type=ScheduleType.ONE_TIME,
        load_test_config={"concurrent_users": 10},
        start_time=datetime.now() + timedelta(hours=1)
    )
    
    task = scheduler.create_schedule(config)
    
    assert task.id is not None
    assert task.config.name == "Test Schedule"
    assert len(scheduler.get_all_schedules()) == 1
    assert len(scheduler.get_active_schedules()) == 1

def test_schedule_serialization():
    """Test schedule serialization to/from dict"""
    
    config = ScheduleConfig(
        name="Test Schedule",
        schedule_type=ScheduleType.ONE_TIME,
        load_test_config={"concurrent_users": 10},
        start_time=datetime.now() + timedelta(hours=1)
    )
    
    task = ScheduledTask(
        id="test-123",
        config=config,
        status=ScheduleStatus.ACTIVE
    )
    
    # Test to_dict
    task_dict = task.to_dict()
    assert task_dict['id'] == "test-123"
    assert task_dict['config']['name'] == "Test Schedule"
    assert task_dict['status'] == "active"
    
    # Test from_dict
    restored_task = ScheduledTask.from_dict(task_dict)
    assert restored_task.id == task.id
    assert restored_task.config.name == task.config.name
    assert restored_task.status == task.status

if __name__ == "__main__":
    test_schedule_config_validation()
    test_scheduled_task_creation()
    test_scheduler_creation()
    test_schedule_serialization()
    print("All scheduling tests passed!")