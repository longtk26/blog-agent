# FastAPI Dependency Injection Reference

This guide explains the dependency injection (DI) patterns and `Dep` type alias convention used throughout the FastAPI backend.

---

## 🎯 The `Dep` Type Alias Pattern

Instead of repeating `Annotated[Type, Depends(...)]` across routers and constructors, each layer defines and exports its own `Dep` alias.

### 1. Database Session Injection (`src/libs/database/session.py`)

```python
from typing import Annotated
from fastapi import Depends
from sqlmodel import Session, create_engine
from src.configs import config

class DBSessionManager: 
    def __init__(self):
        self.engine = self.create_db_engine(config.db_url)

    def create_db_engine(self, db_url: str):
        return create_engine(db_url)

    def get_session(self):
        with Session(self.engine) as session:
            yield session

SessionDep = Annotated[Session, Depends(DBSessionManager().get_session)]
```

### 2. Repository Interface-to-Implementation Binding (`persistence/`)

The repository imports `SessionDep` and exports the bound interface dependency:

```python
# src/modules/users/infrastructure/persistence/user_repository.py
from typing import Annotated
from fastapi import Depends
from src.modules.users.ports.output import IUserRepository

class UserRepository(IUserRepository):
    def __init__(self, session: SessionDep):
        self.session = session
    ...

# Interface is bound to the concrete class here:
IUserRepoDep = Annotated[IUserRepository, Depends(UserRepository)]
```

### 3. Use Case Injection into Routers (`usecases/`)

The use case imports `IUserRepoDep`, and exports its own `<Name>UsecaseDep`:

```python
# src/modules/users/usecases/create_user_usecase.py
from typing import Annotated
from fastapi import Depends
from src.modules.users.ports.output import IUserRepoDep

class CreateUserUsecase:
    def __init__(self, user_repo: IUserRepoDep):
        self.user_repo = user_repo
    ...

CreateUserUsecaseDep = Annotated[CreateUserUsecase, Depends(CreateUserUsecase)]
```

For use cases without a repository dependency (e.g. `health_check_usecase.py`), direct dependency is used:

```python
# src/modules/health/usecases/health_check_usecase.py
from typing import Annotated
from fastapi import Depends

class HealthCheckUsecase:
    def execute(self) -> dict:
        return {"status": "ok"}

HealthCheckUsecaseDep = Annotated[HealthCheckUsecase, Depends(HealthCheckUsecase)]
```

### 4. Router Handler Injection (`presenter/router.py`)

Routers simply specify the `<Name>UsecaseDep` in route parameters:

```python
# src/modules/users/presenter/router.py
from fastapi import APIRouter
from src.modules.users.usecases import CreateUserUsecaseDep
from src.modules.users.presenter.dtos import CreateUserRequestDto, CreateUserResponseDto

user_router = APIRouter(prefix="/users", tags=["users"])

@user_router.post("", response_model=CreateUserResponseDto)
async def create_user(user: CreateUserRequestDto, usecase: CreateUserUsecaseDep) -> CreateUserResponseDto:
    return await usecase.execute(user)
```

---

## ⛓️ Resolution Chain Flow

```text
Request Arrives
    │
    ▼
router handler: `create_user(..., usecase: CreateUserUsecaseDep)`
    │
    ▼
FastAPI instantiates `CreateUserUsecase(user_repo: IUserRepoDep)`
    │
    ▼
FastAPI resolves `IUserRepoDep` -> instantiates `UserRepository(session: SessionDep)`
    │
    ▼
FastAPI resolves `SessionDep` -> executes `DBSessionManager().get_session()`
```
