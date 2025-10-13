"""
Endpoint Selection Logic for Load Testing Automation
"""
import random
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
from config import config_manager

logger = logging.getLogger(__name__)

@dataclass
class EndpointConfig:
    """Configuration for a single endpoint"""
    name: str
    url: str
    method: str = "GET"
    weight: float = 1.0
    timeout: int = 30
    description: str = ""
    enabled: bool = True

@dataclass
class EndpointStats:
    """Statistics for a single endpoint"""
    name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    last_accessed: Optional[datetime] = None
    
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

class EndpointSelector:
    """
    Handles endpoint selection with weighted random algorithm
    and tracks endpoint statistics
    """
    
    def __init__(self):
        self.endpoints: Dict[str, EndpointConfig] = {}
        self.stats: Dict[str, EndpointStats] = {}
        self._load_endpoints()
    
    def _load_endpoints(self):
        """Load endpoint configurations from config manager"""
        try:
            endpoints_config = config_manager.get_endpoints_config()
            target_url = config_manager.config.get("target_app_url", "http://app:5000")
            
            # Define performance problem endpoints as specified in requirements
            default_endpoints = {
                "/performance/slow": {
                    "description": "Slow processing endpoint",
                    "weight": 1.0,
                    "enabled": True
                },
                "/performance/n-plus-one": {
                    "description": "N+1 query problem endpoint", 
                    "weight": 1.0,
                    "enabled": True
                },
                "/performance/slow-query": {
                    "description": "Slow database query endpoint",
                    "weight": 1.0,
                    "enabled": True
                },
                "/performance/js-errors": {
                    "description": "JavaScript errors endpoint",
                    "weight": 1.0,
                    "enabled": True
                },
                "/performance/bad-vitals": {
                    "description": "Bad Core Web Vitals endpoint",
                    "weight": 1.0,
                    "enabled": True
                },
                "/performance/error": {
                    "description": "General application error endpoint",
                    "weight": 1.0,
                    "enabled": True,
                    "timeout": 30
                },
                "/performance/slow-query/full-scan": {
                    "description": "Full table scan database query endpoint",
                    "weight": 1.0,
                    "enabled": True,
                    "timeout": 60
                },
                "/performance/slow-query/complex-join": {
                    "description": "Complex join database query endpoint",
                    "weight": 1.0,
                    "enabled": True,
                    "timeout": 60
                }
            }
            
            # Merge with config file settings
            for path, default_config in default_endpoints.items():
                config = endpoints_config.get(path, default_config)
                
                endpoint = EndpointConfig(
                    name=path,
                    url=f"{target_url.rstrip('/')}{path}",
                    method="GET",
                    weight=config.get("weight", default_config["weight"]),
                    timeout=config.get("timeout", default_config.get("timeout", 30)),
                    description=config.get("description", default_config["description"]),
                    enabled=config.get("enabled", default_config["enabled"])
                )
                
                self.endpoints[path] = endpoint
                
                # Initialize stats if not exists
                if path not in self.stats:
                    self.stats[path] = EndpointStats(name=path)
            
            logger.info(f"Loaded {len(self.endpoints)} endpoints")
            
        except Exception as e:
            logger.error(f"Error loading endpoints: {e}")
            raise
    
    def select_endpoint(self) -> Optional[EndpointConfig]:
        """
        Select an endpoint using weighted random selection
        Returns None if no enabled endpoints are available
        """
        try:
            # Get enabled endpoints only
            enabled_endpoints = {
                name: endpoint for name, endpoint in self.endpoints.items() 
                if endpoint.enabled
            }
            
            if not enabled_endpoints:
                logger.warning("No enabled endpoints available for selection")
                return None
            
            # Create weighted list for selection
            endpoints_list = list(enabled_endpoints.values())
            weights = [endpoint.weight for endpoint in endpoints_list]
            
            # Use weighted random selection
            selected_endpoint = random.choices(endpoints_list, weights=weights, k=1)[0]
            
            logger.debug(f"Selected endpoint: {selected_endpoint.name}")
            return selected_endpoint
            
        except Exception as e:
            logger.error(f"Error selecting endpoint: {e}")
            return None
    
    def update_weights(self, weights: Dict[str, float]) -> bool:
        """
        Update endpoint weights
        Returns True if successful, False otherwise
        """
        try:
            updated_config = {}
            endpoints_config = config_manager.get_endpoints_config()
            
            for endpoint_name, weight in weights.items():
                if endpoint_name in self.endpoints:
                    # Update in-memory endpoint
                    self.endpoints[endpoint_name].weight = weight
                    
                    # Prepare config update
                    if endpoint_name not in updated_config:
                        updated_config[endpoint_name] = endpoints_config.get(endpoint_name, {})
                    updated_config[endpoint_name]["weight"] = weight
            
            # Update configuration file
            if updated_config:
                config_update = {"endpoints": {**endpoints_config, **updated_config}}
                success = config_manager.update_config(config_update)
                
                if success:
                    logger.info(f"Updated weights for {len(updated_config)} endpoints")
                    return True
                else:
                    logger.error("Failed to update configuration file")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating weights: {e}")
            return False
    
    def get_endpoint_stats(self) -> Dict[str, EndpointStats]:
        """Get statistics for all endpoints"""
        return self.stats.copy()
    
    def update_endpoint_stats(self, endpoint_name: str, success: bool, response_time: float = 0.0):
        """
        Update statistics for an endpoint after a request
        
        Args:
            endpoint_name: Name of the endpoint
            success: Whether the request was successful
            response_time: Response time in seconds
        """
        try:
            if endpoint_name not in self.stats:
                self.stats[endpoint_name] = EndpointStats(name=endpoint_name)
            
            stats = self.stats[endpoint_name]
            stats.total_requests += 1
            stats.last_accessed = datetime.now()
            
            if success:
                stats.successful_requests += 1
                stats.total_response_time += response_time
            else:
                stats.failed_requests += 1
            
            logger.debug(f"Updated stats for {endpoint_name}: {stats.total_requests} total requests")
            
        except Exception as e:
            logger.error(f"Error updating endpoint stats: {e}")
    
    def get_enabled_endpoints(self) -> List[EndpointConfig]:
        """Get list of enabled endpoints"""
        return [endpoint for endpoint in self.endpoints.values() if endpoint.enabled]
    
    def get_endpoint_by_name(self, name: str) -> Optional[EndpointConfig]:
        """Get endpoint configuration by name"""
        return self.endpoints.get(name)
    
    def reload_endpoints(self):
        """Reload endpoint configurations from config manager"""
        self._load_endpoints()
    
    def get_endpoint_summary(self) -> Dict:
        """Get summary of all endpoints with their current status"""
        summary = {
            "total_endpoints": len(self.endpoints),
            "enabled_endpoints": len(self.get_enabled_endpoints()),
            "endpoints": {}
        }
        
        for name, endpoint in self.endpoints.items():
            stats = self.stats.get(name, EndpointStats(name=name))
            summary["endpoints"][name] = {
                "url": endpoint.url,
                "weight": endpoint.weight,
                "enabled": endpoint.enabled,
                "description": endpoint.description,
                "total_requests": stats.total_requests,
                "success_rate": stats.success_rate,
                "average_response_time": stats.average_response_time,
                "last_accessed": stats.last_accessed.isoformat() if stats.last_accessed else None
            }
        
        return summary

# Global endpoint selector instance
endpoint_selector = EndpointSelector()