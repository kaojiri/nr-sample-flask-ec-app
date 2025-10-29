"""
User Session Management System for Load Testing Automation
"""
import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json
from pathlib import Path

from http_client import AsyncHTTPClient, RequestResult
from config import config_manager

logger = logging.getLogger(__name__)

@dataclass
class TestUser:
    """Test user account configuration"""
    user_id: str
    username: str
    password: str
    enabled: bool = True
    description: str = ""
    test_batch_id: Optional[str] = None
    is_bulk_created: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "password": self.password,
            "enabled": self.enabled,
            "description": self.description,
            "test_batch_id": self.test_batch_id,
            "is_bulk_created": self.is_bulk_created
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestUser':
        """Create TestUser from dictionary"""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            password=data["password"],
            enabled=data.get("enabled", True),
            description=data.get("description", ""),
            test_batch_id=data.get("test_batch_id"),
            is_bulk_created=data.get("is_bulk_created", False)
        )

@dataclass
class UserSession:
    """User session with authentication state"""
    user_id: str
    username: str
    session_cookie: str
    login_time: datetime
    last_used: datetime
    is_valid: bool = True
    login_attempts: int = 0
    last_login_error: Optional[str] = None
    
    def __post_init__(self):
        if isinstance(self.login_time, str):
            self.login_time = datetime.fromisoformat(self.login_time)
        if isinstance(self.last_used, str):
            self.last_used = datetime.fromisoformat(self.last_used)
    
    @property
    def is_expired(self) -> bool:
        """Check if session is expired (older than 1 hour)"""
        return datetime.now() - self.last_used > timedelta(hours=1)
    
    @property
    def age_minutes(self) -> float:
        """Get session age in minutes"""
        return (datetime.now() - self.login_time).total_seconds() / 60
    
    def update_last_used(self):
        """Update last used timestamp"""
        self.last_used = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "session_cookie": self.session_cookie,
            "login_time": self.login_time.isoformat(),
            "last_used": self.last_used.isoformat(),
            "is_valid": self.is_valid,
            "login_attempts": self.login_attempts,
            "last_login_error": self.last_login_error
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserSession':
        """Create UserSession from dictionary"""
        return cls(
            user_id=data["user_id"],
            username=data["username"],
            session_cookie=data["session_cookie"],
            login_time=data["login_time"],
            last_used=data["last_used"],
            is_valid=data.get("is_valid", True),
            login_attempts=data.get("login_attempts", 0),
            last_login_error=data.get("last_login_error")
        )

@dataclass
class SessionStats:
    """Statistics for user session management"""
    total_users: int = 0
    active_sessions: int = 0
    expired_sessions: int = 0
    failed_logins: int = 0
    successful_logins: int = 0
    last_login_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        """Calculate login success rate"""
        total_attempts = self.successful_logins + self.failed_logins
        if total_attempts == 0:
            return 0.0
        return (self.successful_logins / total_attempts) * 100.0
    
    @property
    def total_sessions(self) -> int:
        """Total number of sessions (active + expired)"""
        return self.active_sessions + self.expired_sessions
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "total_users": self.total_users,
            "active_sessions": self.active_sessions,
            "expired_sessions": self.expired_sessions,
            "failed_logins": self.failed_logins,
            "successful_logins": self.successful_logins,
            "success_rate": self.success_rate,
            "total_sessions": self.total_sessions,
            "last_login_time": self.last_login_time.isoformat() if self.last_login_time else None
        }

class UserSessionManager:
    """
    Manages user sessions for load testing with multiple user accounts
    """
    
    def __init__(self, target_app_url: str = None):
        self.target_app_url = target_app_url or config_manager.get_config().get("target_app_url", "http://app:5000")
        self.test_users: Dict[str, TestUser] = {}
        self.active_sessions: Dict[str, UserSession] = {}
        self._http_client: Optional[AsyncHTTPClient] = None
        self._login_lock = asyncio.Lock()
        
        # Statistics
        self.stats = SessionStats()
        
        # Load test users from configuration
        self._load_test_users()
    
    def _load_test_users(self):
        """Load test users from configuration"""
        try:
            # Clear existing users first
            self.test_users.clear()
            
            config = config_manager.get_config()
            users_config = config.get("test_users", [])
            
            logger.debug(f"Raw users config: {users_config}")
            
            for user_data in users_config:
                logger.debug(f"Processing user data: {user_data}")
                user = TestUser.from_dict(user_data)
                logger.debug(f"Created user: {user}")
                self.test_users[user.user_id] = user
            
            self.stats.total_users = len(self.test_users)
            logger.info(f"Loaded {len(self.test_users)} test users from configuration")
            
        except Exception as e:
            logger.error(f"Error loading test users: {e}")
            # Don't create default test users - let users add them manually
    
    def reload_test_users(self):
        """Reload test users from configuration"""
        self._load_test_users()
    
    def _create_default_test_users(self):
        """Create default test users for testing"""
        default_users = [
            TestUser(
                user_id="test_user_1",
                username="testuser1@example.com",
                password="password123",
                description="Default test user 1"
            ),
            TestUser(
                user_id="test_user_2", 
                username="testuser2@example.com",
                password="password123",
                description="Default test user 2"
            ),
            TestUser(
                user_id="test_user_3",
                username="testuser3@example.com", 
                password="password123",
                description="Default test user 3"
            )
        ]
        
        for user in default_users:
            self.test_users[user.user_id] = user
        
        self.stats.total_users = len(self.test_users)
        logger.info(f"Created {len(default_users)} default test users")
    
    async def login_all_users(self) -> Dict[str, UserSession]:
        """
        Login all enabled test users and return their sessions
        
        Returns:
            Dictionary mapping user_id to UserSession
        """
        try:
            login_tasks = []
            enabled_users = [user for user in self.test_users.values() if user.enabled]
            
            logger.info(f"Total test users: {len(self.test_users)}")
            logger.info(f"Enabled users: {len(enabled_users)}")
            for user in enabled_users:
                logger.info(f"Enabled user: {user.user_id} - {user.username}")
            
            for user in enabled_users:
                task = asyncio.create_task(self._login_user(user))
                login_tasks.append(task)
                
            # Execute all login attempts concurrently
            results = await asyncio.gather(*login_tasks, return_exceptions=True)
                
            # Process results
            successful_sessions = {}
            for i, result in enumerate(results):
                user = enabled_users[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Login failed for user {user.username}: {result}")
                    self.stats.failed_logins += 1
                elif result:
                    successful_sessions[user.user_id] = result
                    self.active_sessions[user.user_id] = result
                    self.stats.successful_logins += 1
                    self.stats.last_login_time = datetime.now()
                else:
                    logger.warning(f"Login returned None for user {user.username}")
                    self.stats.failed_logins += 1
            
            self.stats.active_sessions = len(self.active_sessions)
            logger.info(f"Successfully logged in {len(successful_sessions)} out of {len(enabled_users)} users")
            
            return successful_sessions
                
        except Exception as e:
            logger.error(f"Error during bulk user login: {e}")
            return {}
    
    async def _login_user(self, user: TestUser) -> Optional[UserSession]:
        """
        Login a single user and return session
        
        Args:
            user: TestUser to login
            
        Returns:
            UserSession if successful, None otherwise
        """
        try:
            import aiohttp
            import urllib.parse
            
            async with self._login_lock:
                login_url = f"{self.target_app_url}/auth/login"
                login_data = {
                    "email": user.username,  # Flask EC app expects 'email' field
                    "password": user.password
                }
                
                logger.debug(f"Attempting login for user {user.username}")
                
                # Use aiohttp directly for more reliable HTTP requests
                async with aiohttp.ClientSession() as session:
                    # Encode form data as application/x-www-form-urlencoded (not multipart/form-data)
                    form_data = {
                        'email': user.username,
                        'password': user.password
                    }

                    logger.debug(f"Making request to {login_url}")
                    logger.debug(f"Login credentials: email={user.username}, password={'*' * len(user.password)}")

                    async with session.post(login_url, data=form_data, allow_redirects=False) as response:
                        logger.debug(f"Request completed: {response.status}")
                        logger.debug(f"Response headers: {dict(response.headers)}")
                        
                        # Check if login was successful (200 or 302 redirect)
                        if response.status in [200, 302]:
                            # Extract session cookie from response headers
                            set_cookie_headers = response.headers.getall('Set-Cookie', [])
                            logger.debug(f"Set-Cookie headers: {set_cookie_headers}")
                            
                            if set_cookie_headers:
                                # Try to extract session cookie from any Set-Cookie header
                                session_cookie = None
                                for set_cookie in set_cookie_headers:
                                    session_cookie = self._extract_session_cookie_from_header(set_cookie)
                                    if session_cookie:
                                        break
                                
                                if session_cookie:
                                    user_session = UserSession(
                                        user_id=user.user_id,
                                        username=user.username,
                                        session_cookie=session_cookie,
                                        login_time=datetime.now(),
                                        last_used=datetime.now()
                                    )
                                    
                                    logger.info(f"Successfully logged in user {user.username}")
                                    return user_session
                                else:
                                    logger.warning(f"No session cookie found for user {user.username}")
                            else:
                                logger.warning(f"No Set-Cookie header found for user {user.username}")
                        else:
                            logger.warning(f"Login failed for user {user.username}: HTTP {response.status}")
                            
                        return None
                    
        except Exception as e:
            import traceback
            logger.error(f"Error logging in user {user.username}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _extract_session_cookie_from_header(self, set_cookie_header: str) -> Optional[str]:
        """
        Extract session cookie from Set-Cookie header string
        
        Args:
            set_cookie_header: Set-Cookie header value
            
        Returns:
            Session cookie value if found, None otherwise
        """
        try:
            # Parse session cookie (Flask default session cookie name is 'session')
            # Format: "session=value; Path=/; HttpOnly"
            cookies = set_cookie_header.split(';')
            for cookie in cookies:
                cookie = cookie.strip()
                if cookie.startswith('session='):
                    session_value = cookie.split('=', 1)[1]
                    logger.debug(f"Extracted session cookie: {session_value[:20]}...")
                    return session_value
            
            logger.warning("Session cookie not found in Set-Cookie header")
            return None
        except Exception as e:
            logger.error(f"Error parsing session cookie: {e}")
            return None
    
    def _extract_session_cookie(self, result: RequestResult) -> Optional[str]:
        """
        Extract session cookie from login response
        
        Args:
            result: RequestResult from login request
            
        Returns:
            Session cookie string if found, None otherwise
        """
        if not result.is_success or not result.response_headers:
            return None
        
        # Look for Set-Cookie header
        set_cookie_header = result.response_headers.get('Set-Cookie') or result.response_headers.get('set-cookie')
        
        if not set_cookie_header:
            logger.warning("No Set-Cookie header found in login response")
            return None
        
        # Parse session cookie (Flask default session cookie name is 'session')
        # Format: "session=value; Path=/; HttpOnly"
        cookies = set_cookie_header.split(';')
        for cookie in cookies:
            cookie = cookie.strip()
            if cookie.startswith('session='):
                session_value = cookie.split('=', 1)[1]
                logger.debug(f"Extracted session cookie: {session_value[:20]}...")
                return session_value
        
        logger.warning("Session cookie not found in Set-Cookie header")
        return None
    
    def get_random_session(self) -> Optional[UserSession]:
        """
        Get a random active session for load testing
        
        Returns:
            Random UserSession if available, None otherwise
        """
        try:
            # Filter valid, non-expired sessions
            valid_sessions = [
                session for session in self.active_sessions.values()
                if session.is_valid and not session.is_expired
            ]
            
            if not valid_sessions:
                logger.warning("No valid sessions available for random selection")
                return None
            
            # Select random session
            selected_session = random.choice(valid_sessions)
            selected_session.update_last_used()
            
            logger.debug(f"Selected random session for user {selected_session.username}")
            return selected_session
            
        except Exception as e:
            logger.error(f"Error selecting random session: {e}")
            return None
    
    async def refresh_expired_sessions(self) -> int:
        """
        Refresh expired sessions by re-logging in users
        
        Returns:
            Number of sessions successfully refreshed
        """
        try:
            expired_sessions = [
                session for session in self.active_sessions.values()
                if session.is_expired or not session.is_valid
            ]
            
            if not expired_sessions:
                return 0
            
            logger.info(f"Refreshing {len(expired_sessions)} expired sessions")
            
            refreshed_count = 0
            for session in expired_sessions:
                user = self.test_users.get(session.user_id)
                if user and user.enabled:
                    new_session = await self._login_user(user)
                    if new_session:
                        self.active_sessions[session.user_id] = new_session
                        refreshed_count += 1
                        logger.debug(f"Refreshed session for user {user.username}")
                    else:
                        # Mark session as invalid but keep it for statistics
                        session.is_valid = False
                        logger.warning(f"Failed to refresh session for user {user.username}")
                else:
                    # Remove session for disabled/missing users
                    if session.user_id in self.active_sessions:
                        del self.active_sessions[session.user_id]
            
            self.stats.active_sessions = len([s for s in self.active_sessions.values() if s.is_valid])
            self.stats.expired_sessions = len([s for s in self.active_sessions.values() if s.is_expired])
            
            logger.info(f"Successfully refreshed {refreshed_count} out of {len(expired_sessions)} expired sessions")
            return refreshed_count
            
        except Exception as e:
            logger.error(f"Error refreshing expired sessions: {e}")
            return 0
    
    async def logout_all_users(self) -> int:
        """
        Logout all users and clear sessions
        
        Returns:
            Number of users logged out
        """
        try:
            logout_count = len(self.active_sessions)
            
            # In a real implementation, you might want to make logout requests
            # to the target application to properly invalidate sessions
            
            # Clear all sessions
            self.active_sessions.clear()
            
            # Update statistics
            self.stats.active_sessions = 0
            self.stats.expired_sessions = 0
            
            logger.info(f"Logged out {logout_count} users")
            return logout_count
            
        except Exception as e:
            logger.error(f"Error logging out users: {e}")
            return 0
    
    def get_session_stats(self) -> SessionStats:
        """Get current session statistics"""
        try:
            # Update real-time statistics
            valid_sessions = [s for s in self.active_sessions.values() if s.is_valid and not s.is_expired]
            expired_sessions = [s for s in self.active_sessions.values() if s.is_expired]
            
            self.stats.active_sessions = len(valid_sessions)
            self.stats.expired_sessions = len(expired_sessions)
            
            return self.stats
            
        except Exception as e:
            logger.error(f"Error getting session stats: {e}")
            return SessionStats()
    
    def add_test_user(self, user: TestUser) -> bool:
        """
        Add a new test user
        
        Args:
            user: TestUser to add
            
        Returns:
            True if added successfully, False otherwise
        """
        try:
            if user.user_id in self.test_users:
                logger.warning(f"User {user.user_id} already exists")
                return False
            
            self.test_users[user.user_id] = user
            self.stats.total_users = len(self.test_users)
            
            logger.info(f"Added test user {user.username}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding test user: {e}")
            return False
    
    def remove_test_user(self, user_id: str) -> bool:
        """
        Remove a test user
        
        Args:
            user_id: ID of user to remove
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            if user_id not in self.test_users:
                logger.warning(f"User {user_id} not found")
                return False
            
            # Remove user and any active session
            del self.test_users[user_id]
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
            
            self.stats.total_users = len(self.test_users)
            self.stats.active_sessions = len([s for s in self.active_sessions.values() if s.is_valid])
            
            logger.info(f"Removed test user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing test user: {e}")
            return False
    
    def get_test_users(self) -> List[TestUser]:
        """Get list of all test users"""
        return list(self.test_users.values())
    
    def get_active_sessions(self) -> List[UserSession]:
        """Get list of all active sessions"""
        return [s for s in self.active_sessions.values() if s.is_valid and not s.is_expired]
    
    def update_test_users_config(self, users: List[TestUser]) -> bool:
        """
        Update test users configuration and save to config file
        
        Args:
            users: List of TestUser objects
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            # Update internal users dictionary
            self.test_users.clear()
            for user in users:
                self.test_users[user.user_id] = user
            
            # Update configuration file using config_manager's method
            user_dicts = [user.to_dict() for user in users]
            
            if config_manager.update_test_users_config(user_dicts):
                self.stats.total_users = len(self.test_users)
                logger.info(f"Updated test users configuration with {len(users)} users")
                return True
            else:
                logger.error("Failed to save test users configuration")
                return False
                
        except Exception as e:
            logger.error(f"Error updating test users configuration: {e}")
            return False
    
    def get_users_by_batch(self, batch_id: str) -> List[TestUser]:
        """
        Get users by batch ID
        
        Args:
            batch_id: Batch ID to filter by
            
        Returns:
            List of TestUser objects in the batch
        """
        try:
            batch_users = [
                user for user in self.test_users.values()
                if user.test_batch_id == batch_id
            ]
            logger.debug(f"Found {len(batch_users)} users in batch {batch_id}")
            return batch_users
        except Exception as e:
            logger.error(f"Error getting users by batch {batch_id}: {e}")
            return []
    
    def get_all_batches(self) -> List[str]:
        """
        Get all unique batch IDs
        
        Returns:
            List of unique batch IDs
        """
        try:
            batch_ids = set()
            for user in self.test_users.values():
                if user.test_batch_id:
                    batch_ids.add(user.test_batch_id)
            return list(batch_ids)
        except Exception as e:
            logger.error(f"Error getting all batches: {e}")
            return []
    
    async def login_batch_users(self, batch_id: str) -> Dict[str, UserSession]:
        """
        Login all users in a specific batch
        
        Args:
            batch_id: Batch ID to login
            
        Returns:
            Dictionary mapping user_id to UserSession for successful logins
        """
        try:
            batch_users = self.get_users_by_batch(batch_id)
            enabled_users = [user for user in batch_users if user.enabled]
            
            logger.info(f"Logging in {len(enabled_users)} users from batch {batch_id}")
            
            login_tasks = []
            for user in enabled_users:
                task = asyncio.create_task(self._login_user(user))
                login_tasks.append(task)
            
            # Execute all login attempts concurrently
            results = await asyncio.gather(*login_tasks, return_exceptions=True)
            
            # Process results
            successful_sessions = {}
            for i, result in enumerate(results):
                user = enabled_users[i]
                
                if isinstance(result, Exception):
                    logger.error(f"Login failed for user {user.username}: {result}")
                    self.stats.failed_logins += 1
                elif result:
                    successful_sessions[user.user_id] = result
                    self.active_sessions[user.user_id] = result
                    self.stats.successful_logins += 1
                    self.stats.last_login_time = datetime.now()
                else:
                    logger.warning(f"Login returned None for user {user.username}")
                    self.stats.failed_logins += 1
            
            self.stats.active_sessions = len([s for s in self.active_sessions.values() if s.is_valid])
            logger.info(f"Successfully logged in {len(successful_sessions)} out of {len(enabled_users)} users from batch {batch_id}")
            
            return successful_sessions
            
        except Exception as e:
            logger.error(f"Error during batch user login for batch {batch_id}: {e}")
            return {}
    
    def remove_batch_users(self, batch_id: str) -> int:
        """
        Remove all users from a specific batch
        
        Args:
            batch_id: Batch ID to remove
            
        Returns:
            Number of users removed
        """
        try:
            batch_users = self.get_users_by_batch(batch_id)
            removed_count = 0
            
            for user in batch_users:
                if self.remove_test_user(user.user_id):
                    removed_count += 1
            
            logger.info(f"Removed {removed_count} users from batch {batch_id}")
            return removed_count
            
        except Exception as e:
            logger.error(f"Error removing batch users for batch {batch_id}: {e}")
            return 0
    
    def get_batch_session_stats(self, batch_id: str) -> Dict[str, Any]:
        """
        Get session statistics for a specific batch
        
        Args:
            batch_id: Batch ID to get stats for
            
        Returns:
            Dictionary with batch session statistics
        """
        try:
            batch_users = self.get_users_by_batch(batch_id)
            batch_sessions = [
                session for session in self.active_sessions.values()
                if any(user.user_id == session.user_id for user in batch_users)
            ]
            
            active_sessions = [s for s in batch_sessions if s.is_valid and not s.is_expired]
            expired_sessions = [s for s in batch_sessions if s.is_expired]
            
            return {
                "batch_id": batch_id,
                "total_users": len(batch_users),
                "total_sessions": len(batch_sessions),
                "active_sessions": len(active_sessions),
                "expired_sessions": len(expired_sessions),
                "session_details": [
                    {
                        "user_id": session.user_id,
                        "username": session.username,
                        "is_valid": session.is_valid,
                        "is_expired": session.is_expired,
                        "age_minutes": session.age_minutes
                    }
                    for session in batch_sessions
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting batch session stats for batch {batch_id}: {e}")
            return {
                "batch_id": batch_id,
                "error": str(e)
            }
    
    def remove_user_by_username(self, username: str) -> bool:
        """
        ユーザー名でユーザーを削除（ライフサイクル管理用）
        要件 3.1: バッチ単位でのテストユーザー削除機能
        
        Args:
            username: 削除するユーザー名
            
        Returns:
            True if removed successfully, False otherwise
        """
        try:
            # ユーザー名でユーザーを検索
            user_to_remove = None
            for user in self.test_users.values():
                if user.username == username:
                    user_to_remove = user
                    break
            
            if user_to_remove:
                return self.remove_test_user(user_to_remove.user_id)
            else:
                logger.warning(f"User with username {username} not found")
                return False
                
        except Exception as e:
            logger.error(f"Error removing user by username {username}: {e}")
            return False
    
    def clear_all_sessions(self) -> int:
        """
        全てのセッションをクリア（ライフサイクル管理用）
        要件 3.1: バッチ単位でのテストユーザー削除機能
        
        Returns:
            Number of sessions cleared
        """
        try:
            cleared_count = len(self.active_sessions)
            self.active_sessions.clear()
            
            # 統計を更新
            self.stats.active_sessions = 0
            self.stats.expired_sessions = 0
            
            logger.info(f"Cleared {cleared_count} sessions")
            return cleared_count
            
        except Exception as e:
            logger.error(f"Error clearing all sessions: {e}")
            return 0
    
    def identify_test_users_by_criteria(self, criteria: Dict[str, Any]) -> Dict[str, List[TestUser]]:
        """
        条件に基づいてテストユーザーを識別
        要件 3.2: テストユーザーと本番ユーザーの識別機能
        
        Args:
            criteria: 識別条件（batch_id, is_bulk_created等）
            
        Returns:
            Dictionary with categorized users
        """
        try:
            matching_users = []
            non_matching_users = []
            
            for user in self.test_users.values():
                matches = True
                
                # バッチIDでフィルタ
                if 'batch_id' in criteria:
                    if user.test_batch_id != criteria['batch_id']:
                        matches = False
                
                # 一括作成フラグでフィルタ
                if 'is_bulk_created' in criteria:
                    if user.is_bulk_created != criteria['is_bulk_created']:
                        matches = False
                
                # 有効フラグでフィルタ
                if 'enabled' in criteria:
                    if user.enabled != criteria['enabled']:
                        matches = False
                
                if matches:
                    matching_users.append(user)
                else:
                    non_matching_users.append(user)
            
            return {
                'matching_users': matching_users,
                'non_matching_users': non_matching_users,
                'total_matching': len(matching_users),
                'total_non_matching': len(non_matching_users),
                'criteria': criteria,
                'identification_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error identifying test users by criteria: {e}")
            return {
                'error': str(e),
                'criteria': criteria,
                'identification_timestamp': datetime.now().isoformat()
            }
    
    def generate_lifecycle_report(self) -> Dict[str, Any]:
        """
        ライフサイクルレポートを生成
        要件 3.3: クリーンアップレポート生成機能
        
        Returns:
            Dictionary with lifecycle report
        """
        try:
            # 基本統計
            total_users = len(self.test_users)
            enabled_users = len([user for user in self.test_users.values() if user.enabled])
            bulk_created_users = len([user for user in self.test_users.values() if user.is_bulk_created])
            
            # バッチ統計
            batches = self.get_all_batches()
            batch_details = []
            
            for batch_id in batches:
                batch_users = self.get_users_by_batch(batch_id)
                batch_stats = self.get_batch_session_stats(batch_id)
                
                batch_details.append({
                    'batch_id': batch_id,
                    'user_count': len(batch_users),
                    'enabled_count': len([user for user in batch_users if user.enabled]),
                    'bulk_created_count': len([user for user in batch_users if user.is_bulk_created]),
                    'active_sessions': batch_stats.get('active_sessions', 0),
                    'total_sessions': batch_stats.get('total_sessions', 0)
                })
            
            # セッション統計
            session_stats = self.get_session_stats()
            
            return {
                'total_users': total_users,
                'enabled_users': enabled_users,
                'bulk_created_users': bulk_created_users,
                'total_batches': len(batches),
                'batch_details': batch_details,
                'session_statistics': session_stats.to_dict(),
                'system': 'load_tester',
                'report_timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generating lifecycle report: {e}")
            return {
                'error': str(e),
                'system': 'load_tester',
                'report_timestamp': datetime.now().isoformat()
            }
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """
        古いセッションをクリーンアップ
        
        Args:
            max_age_hours: 最大セッション保持時間（時間）
            
        Returns:
            Number of sessions cleaned up
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            old_sessions = []
            
            for user_id, session in list(self.active_sessions.items()):
                if session.login_time < cutoff_time:
                    old_sessions.append(user_id)
            
            # 古いセッションを削除
            for user_id in old_sessions:
                del self.active_sessions[user_id]
            
            # 統計を更新
            self.stats.active_sessions = len([s for s in self.active_sessions.values() if s.is_valid])
            self.stats.expired_sessions = len([s for s in self.active_sessions.values() if s.is_expired])
            
            logger.info(f"Cleaned up {len(old_sessions)} old sessions (older than {max_age_hours} hours)")
            return len(old_sessions)
            
        except Exception as e:
            logger.error(f"Error cleaning up old sessions: {e}")
            return 0
    
    async def close(self):
        """Close HTTP client and cleanup resources"""
        try:
            if self._http_client:
                await self._http_client.close()
                self._http_client = None
            
            logger.debug("User session manager closed")
            
        except Exception as e:
            logger.error(f"Error closing user session manager: {e}")

# Global user session manager instance
user_session_manager: Optional[UserSessionManager] = None

def get_user_session_manager() -> UserSessionManager:
    """Get global user session manager instance"""
    global user_session_manager
    if user_session_manager is None:
        user_session_manager = UserSessionManager()
    return user_session_manager

def reset_user_session_manager():
    """Reset global user session manager instance to reload configuration"""
    global user_session_manager
    if user_session_manager:
        # Close existing HTTP client if any
        if user_session_manager._http_client:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(user_session_manager.close())
                else:
                    asyncio.run(user_session_manager.close())
            except:
                pass
    user_session_manager = None