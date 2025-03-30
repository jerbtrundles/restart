"""
plugins/service_locator.py
Service locator for plugin dependencies.

This implements the service locator pattern to further reduce coupling
between plugins and other components.
"""
from typing import Dict, Any, Optional, Type, List
import inspect


class ServiceNotFoundException(Exception):
    """Exception raised when a requested service is not found."""
    pass


class ServiceLocator:
    """
    Service locator for finding and using services.
    
    This provides a central registry of services that plugins can use
    without directly depending on specific implementations.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'ServiceLocator':
        """
        Get the singleton instance of the service locator.
        
        Returns:
            The service locator instance.
        """
        if cls._instance is None:
            cls._instance = ServiceLocator()
        return cls._instance
    
    def __init__(self):
        """Initialize the service locator."""
        self._services: Dict[str, Any] = {}
        self._service_by_type: Dict[Type, str] = {}
    
    def register_service(self, service_name: str, service: Any) -> None:
        """
        Register a service with the locator.
        
        Args:
            service_name: The name of the service.
            service: The service instance.
        """
        self._services[service_name] = service
        
        # Register by type for type-based lookups
        if service is not None:
            self._service_by_type[type(service)] = service_name
    
    def get_service(self, service_name: str) -> Any:
        """
        Get a service by name.
        
        Args:
            service_name: The name of the service.
            
        Returns:
            The service instance.
            
        Raises:
            ServiceNotFoundException: If the service is not found.
        """
        if service_name in self._services:
            return self._services[service_name]
        raise ServiceNotFoundException(f"Service '{service_name}' not found")
    
    def get_service_by_type(self, service_type: Type) -> Any:
        """
        Get a service by type.
        
        Args:
            service_type: The type of the service.
            
        Returns:
            The service instance.
            
        Raises:
            ServiceNotFoundException: If no service of the given type is found.
        """
        for service_name, service in self._services.items():
            if isinstance(service, service_type):
                return service
        raise ServiceNotFoundException(f"No service of type '{service_type.__name__}' found")
    
    def get_all_services(self) -> Dict[str, Any]:
        """
        Get all registered services.
        
        Returns:
            A dictionary of service names to service instances.
        """
        return self._services.copy()
    
    def unregister_service(self, service_name: str) -> None:
        """
        Unregister a service.
        
        Args:
            service_name: The name of the service to unregister.
        """
        if service_name in self._services:
            service = self._services[service_name]
            self._services.pop(service_name)
            
            # Also remove from type mapping
            for service_type, name in list(self._service_by_type.items()):
                if name == service_name:
                    self._service_by_type.pop(service_type)
    
    def has_service(self, service_name: str) -> bool:
        """
        Check if a service exists.
        
        Args:
            service_name: The name of the service.
            
        Returns:
            True if the service exists, False otherwise.
        """
        return service_name in self._services
    
    def get_service_names(self) -> List[str]:
        """
        Get a list of all registered service names.
        
        Returns:
            A list of service names.
        """
        return list(self._services.keys())


# Helper function to get service locator instance
def get_service_locator() -> ServiceLocator:
    """
    Get the service locator instance.
    
    Returns:
        The service locator instance.
    """
    return ServiceLocator.get_instance()