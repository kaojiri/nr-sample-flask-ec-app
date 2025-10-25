"""
Asynchronous HTTP Client for Load Testing Automation
"""
import asyncio
import aiohttp
import logging
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from error_handler import error_handler, ErrorType, ErrorAction
from resource_monitor import resource_monitor

logger = logging.getLogger(__name__)

class RequestStatus(Enum):
    """Status of HTTP request"""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    HTTP_ERROR = "http_error"
    UNKNOWN_ERROR = "unknown_error"

@dataclass
class RequestResult:
    """Result of an HTTP request"""
    url: str
    method: str
    status_code: Optional[int] = None
    response_time: float = 0.0
    status: RequestStatus = RequestStatus.UNKNOWN_ERROR
    error_message: Optional[str] = None
    response_size: int = 0
    timestamp: datetime = None
    response_headers: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def is_success(self) -> bool:
        """Check if request was successful"""
        return self.status == RequestStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        """Check if request resulted in an error"""
        return not self.is_success

class AsyncHTTPClient:
    """
    Asynchronous HTTP client for load testing with proper error handling,
    timeout management, and request/response logging
    """
    
    def __init__(self, 
                 default_timeout: int = 30,
                 max_connections: int = 100,
                 max_connections_per_host: int = 30):
        """
        Initialize HTTP client
        
        Args:
            default_timeout: Default request timeout in seconds
            max_connections: Maximum total connections
            max_connections_per_host: Maximum connections per host
        """
        self.default_timeout = default_timeout
        self.max_connections = max_connections
        self.max_connections_per_host = max_connections_per_host
        self._session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self._create_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    async def _create_session(self):
        """Create aiohttp session with proper configuration"""
        try:
            # Create connector with connection limits
            self._connector = aiohttp.TCPConnector(
                limit=self.max_connections,
                limit_per_host=self.max_connections_per_host,
                ttl_dns_cache=300,  # DNS cache TTL
                use_dns_cache=True,
                keepalive_timeout=30,
                enable_cleanup_closed=True
            )
            
            # Create session with timeout configuration
            timeout = aiohttp.ClientTimeout(
                total=self.default_timeout,
                connect=10,  # Connection timeout
                sock_read=self.default_timeout  # Socket read timeout
            )
            
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={
                    'User-Agent': 'LoadTester/1.0 (Automated Load Testing)'
                }
            )
            
            logger.debug("HTTP client session created successfully")
            
        except Exception as e:
            logger.error(f"Error creating HTTP session: {e}")
            raise
    
    async def close(self):
        """Close the HTTP session and connector"""
        try:
            if self._session:
                await self._session.close()
                self._session = None
            
            if self._connector:
                await self._connector.close()
                self._connector = None
                
            logger.debug("HTTP client session closed")
            
        except Exception as e:
            logger.error(f"Error closing HTTP session: {e}")
    
    async def make_request(self, 
                          url: str, 
                          method: str = "GET",
                          timeout: Optional[int] = None,
                          headers: Optional[Dict[str, str]] = None,
                          worker_id: Optional[str] = None,
                          **kwargs) -> RequestResult:
        """
        Make an HTTP request with comprehensive error handling
        
        Args:
            url: Target URL
            method: HTTP method (GET, POST, etc.)
            timeout: Request timeout (overrides default)
            headers: Additional headers
            worker_id: ID of worker making request (for error tracking)
            **kwargs: Additional arguments for aiohttp request
            
        Returns:
            RequestResult with request details and outcome
        """
        start_time = time.time()
        result = RequestResult(url=url, method=method.upper())
        
        # Check connection limit
        if not resource_monitor.acquire_connection():
            result.response_time = time.time() - start_time
            result.status = RequestStatus.CONNECTION_ERROR
            result.error_message = "Connection limit reached"
            logger.warning(f"Connection limit reached for {url}")
            return result
        
        try:
            # Ensure session is created
            if not self._session:
                await self._create_session()
            
            # Prepare request parameters
            request_timeout = timeout or self.default_timeout
            request_headers = headers or {}
            
            # Set custom timeout for this request
            custom_timeout = aiohttp.ClientTimeout(total=request_timeout)
            
            logger.debug(f"Making {method.upper()} request to {url}")
            
            # Make the actual HTTP request
            async with self._session.request(
                method=method.upper(),
                url=url,
                headers=request_headers,
                timeout=custom_timeout,
                **kwargs
            ) as response:
                
                # Calculate response time
                result.response_time = time.time() - start_time
                result.status_code = response.status
                
                # Read response content to get size
                content = await response.read()
                result.response_size = len(content)
                
                # Store response headers
                result.response_headers = dict(response.headers)
                
                # Determine if request was successful
                if 200 <= response.status < 400:
                    result.status = RequestStatus.SUCCESS
                    logger.debug(f"Request successful: {url} - {response.status} - {result.response_time:.3f}s")
                else:
                    result.status = RequestStatus.HTTP_ERROR
                    result.error_message = f"HTTP {response.status}: {response.reason}"
                    logger.warning(f"HTTP error: {url} - {response.status} - {result.response_time:.3f}s")
                    
                    # Handle HTTP error through error handler
                    context = {
                        "endpoint": url,
                        "worker_id": worker_id,
                        "response_time": result.response_time
                    }
                    response_info = {
                        "status_code": response.status,
                        "reason": response.reason
                    }
                    error_handler.handle_http_error(response_info, context)
                
        except asyncio.TimeoutError as e:
            result.response_time = time.time() - start_time
            result.status = RequestStatus.TIMEOUT
            result.error_message = f"Request timeout after {request_timeout}s"
            logger.warning(f"Request timeout: {url} - {result.response_time:.3f}s")
            
            # Handle timeout error through error handler
            context = {
                "endpoint": url,
                "worker_id": worker_id,
                "response_time": result.response_time
            }
            error_handler.handle_network_error(e, context)
            
        except aiohttp.ClientConnectionError as e:
            result.response_time = time.time() - start_time
            result.status = RequestStatus.CONNECTION_ERROR
            result.error_message = f"Connection error: {str(e)}"
            logger.warning(f"Connection error: {url} - {str(e)}")
            
            # Handle connection error through error handler
            context = {
                "endpoint": url,
                "worker_id": worker_id,
                "response_time": result.response_time
            }
            error_handler.handle_network_error(e, context)
            
        except aiohttp.ClientError as e:
            result.response_time = time.time() - start_time
            result.status = RequestStatus.HTTP_ERROR
            result.error_message = f"HTTP client error: {str(e)}"
            logger.warning(f"HTTP client error: {url} - {str(e)}")
            
            # Handle HTTP client error through error handler
            context = {
                "endpoint": url,
                "worker_id": worker_id,
                "response_time": result.response_time
            }
            error_handler.handle_network_error(e, context)
            
        except Exception as e:
            result.response_time = time.time() - start_time
            result.status = RequestStatus.UNKNOWN_ERROR
            result.error_message = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error: {url} - {str(e)}")
            
            # Handle application error through error handler
            context = {
                "endpoint": url,
                "worker_id": worker_id,
                "response_time": result.response_time
            }
            error_handler.handle_application_error(e, context)
        
        finally:
            # Always release connection
            resource_monitor.release_connection()
        
        return result
    
    async def make_get_request(self, url: str, **kwargs) -> RequestResult:
        """Convenience method for GET requests"""
        return await self.make_request(url, method="GET", **kwargs)
    
    async def make_post_request(self, url: str, **kwargs) -> RequestResult:
        """Convenience method for POST requests"""
        return await self.make_request(url, method="POST", **kwargs)
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get information about the current session"""
        if not self._session or not self._connector:
            return {"status": "not_initialized"}
        
        return {
            "status": "active",
            "max_connections": self.max_connections,
            "max_connections_per_host": self.max_connections_per_host,
            "default_timeout": self.default_timeout,
            "connector_closed": self._connector.closed if self._connector else True
        }

class RequestLogger:
    """
    Handles logging of HTTP requests and responses for analysis
    """
    
    def __init__(self, log_file: str = "logs/requests.log"):
        self.log_file = log_file
        self.request_logger = logging.getLogger("load_tester.requests")
        
        # Create file handler for request logs
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.request_logger.addHandler(handler)
        self.request_logger.setLevel(logging.INFO)
    
    def log_request(self, result: RequestResult):
        """Log a request result"""
        try:
            log_data = {
                "url": result.url,
                "method": result.method,
                "status_code": result.status_code,
                "response_time": f"{result.response_time:.3f}s",
                "status": result.status.value,
                "response_size": result.response_size,
                "timestamp": result.timestamp.isoformat()
            }
            
            if result.error_message:
                log_data["error"] = result.error_message
            
            # Format log message
            log_message = " | ".join([f"{k}={v}" for k, v in log_data.items()])
            
            if result.is_success:
                self.request_logger.info(log_message)
            else:
                self.request_logger.warning(log_message)
                
        except Exception as e:
            logger.error(f"Error logging request: {e}")

# Global request logger instance
request_logger = RequestLogger()