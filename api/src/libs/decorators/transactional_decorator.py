import functools
import inspect
from typing import Any, Callable
from sqlmodel import Session


def Transactional(method: Callable) -> Callable:
    """
    Method-level decorator that wraps a method in a database transaction.
    
    - Auto-commits when the method completes successfully
    - Auto-rollbacks when an exception is raised
    
    The decorator expects the class instance (self) to have repository attributes 
    that contain a 'session' property.
    
    Usage:
        class MyService:
            def __init__(self, user_repo: UserRepoDep):
                self.user_repo = user_repo
            
            @transactional
            async def create_user(self, data):
                # This method will be wrapped in a transaction
                user = self.user_repo.create(data)
                return user
            
            async def get_user(self, id):
                # This method won't be wrapped in a transaction
                return self.user_repo.find(id)
    """
    
    def _get_session(instance: Any) -> Session | None:
        """Extract the session from any repository attribute in the instance."""
        for attr_name in dir(instance):
            if attr_name.startswith('_'):
                continue
            try:
                attr = getattr(instance, attr_name)
                if hasattr(attr, 'session') and isinstance(attr.session, Session):
                    return attr.session
            except Exception:
                continue
        return None
    
    # Check if method is async or sync and return appropriate wrapper
    if inspect.iscoroutinefunction(method):
        @functools.wraps(method)
        async def async_wrapper(self, *args, **kwargs):
            session = _get_session(self)
            if session is None:
                # No session found, execute method without transaction
                return await method(self, *args, **kwargs)
            
            try:
                result = await method(self, *args, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                raise
        
        return async_wrapper
    else:
        @functools.wraps(method)
        def sync_wrapper(self, *args, **kwargs):
            session = _get_session(self)
            if session is None:
                # No session found, execute method without transaction
                return method(self, *args, **kwargs)
            
            try:
                result = method(self, *args, **kwargs)
                session.commit()
                return result
            except Exception as e:
                session.rollback()
                raise
        
        return sync_wrapper
