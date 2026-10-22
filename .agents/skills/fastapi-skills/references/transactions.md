# FastAPI Transactions Reference

This guide explains the `@Transactional` method decorator for managing database transactions cleanly in use cases.

---

## ⚙️ How `@Transactional` Works

The `@Transactional` decorator introspects the class instance (`self`) to discover any repository attribute containing a `session` property (`sqlmodel.Session`).

1. **Begins Execution**: Executes the wrapped asynchronous or synchronous method.
2. **Auto-commit**: If the method completes without error, `session.commit()` is called.
3. **Auto-rollback**: If any exception is raised, `session.rollback()` is automatically invoked and the exception is re-raised.
4. **Graceful Fallback**: If no active `session` is detected on `self`, the method executes normally without throwing.

---

## 💻 Decorator Implementation

```python
# src/libs/decorators/transactional_decorator.py
import functools
import inspect
from typing import Any, Callable
from sqlmodel import Session

def Transactional(method: Callable) -> Callable:
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

    if inspect.iscoroutinefunction(method):
        @functools.wraps(method)
        async def async_wrapper(self, *args, **kwargs):
            session = _get_session(self)
            if session is None:
                return await method(self, *args, **kwargs)
            try:
                result = await method(self, *args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
        return async_wrapper
    else:
        @functools.wraps(method)
        def sync_wrapper(self, *args, **kwargs):
            session = _get_session(self)
            if session is None:
                return method(self, *args, **kwargs)
            try:
                result = method(self, *args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
        return sync_wrapper
```

---

## 🎯 Usage in Use Cases

Apply `@Transactional` on the use case `execute` method for database mutations (create, update, delete):

```python
# src/modules/users/usecases/create_user_usecase.py
from src.modules.users.ports.output import IUserRepoDep
from src.libs.decorators.transactional_decorator import Transactional
from src.modules.users.presenter.dtos import CreateUserRequestDto, CreateUserResponseDto

class CreateUserUsecase:
    def __init__(self, user_repo: IUserRepoDep):
        self.user_repo = user_repo

    @Transactional
    async def execute(self, user_dto: CreateUserRequestDto) -> CreateUserResponseDto:
        # Repositories use flush() internally; this transaction commits when execute() returns
        user_entity = self.user_repo.create(user_dto.to_entity())
        return CreateUserResponseDto(id=str(user_entity.id))
```
