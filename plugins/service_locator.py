"""plugins/service_locator.py"""
from typing import Dict, Any, Optional, Type, List
import inspect

class ServiceNotFoundException(Exception):
    pass

class ServiceLocator:
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'ServiceLocator':
        if cls._instance is None:
            cls._instance = ServiceLocator()
        return cls._instance
    
    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._service_by_type: Dict[Type, str] = {}
    
    def register_service(self, service_name: str, service: Any) -> None:
        self._services[service_name] = service
        if service is not None:
            self._service_by_type[type(service)] = service_name
    
    def get_service(self, service_name: str) -> Any:
        if service_name in self._services:
            return self._services[service_name]
        raise ServiceNotFoundException(f"Service '{service_name}' not found")
    
    def get_service_by_type(self, service_type: Type) -> Any:
        for service_name, service in self._services.items():
            if isinstance(service, service_type):
                return service
        raise ServiceNotFoundException(f"No service of type '{service_type.__name__}' found")
    
    def get_all_services(self) -> Dict[str, Any]:
        return self._services.copy()
    
    def unregister_service(self, service_name: str) -> None:
        if service_name in self._services:
            service = self._services[service_name]
            self._services.pop(service_name)
            for service_type, name in list(self._service_by_type.items()):
                if name == service_name:
                    self._service_by_type.pop(service_type)
    
    def has_service(self, service_name: str) -> bool:
        return service_name in self._services
    
    def get_service_names(self) -> List[str]:
        return list(self._services.keys())

def get_service_locator() -> ServiceLocator:
    """
    Get the service locator instance.
    
    Returns:
        The service locator instance.
    """
    return ServiceLocator.get_instance()