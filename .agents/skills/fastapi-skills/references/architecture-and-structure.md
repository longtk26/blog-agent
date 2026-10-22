# FastAPI Architecture & Layering Reference

This guide details the Hexagonal (Clean) Architecture principles and folder organization used in FastAPI projects.

---

## 🏗️ Core Layers and Boundaries

```text
HTTP Request (Client)
       │
       ▼
┌────────────────────────────────────────────────────────┐
│ Presenter Layer (`presenter/router.py`)                │
│ - Accepts Request DTOs                                 │
│ - Validates input automatically via Pydantic           │
│ - Calls Use Case and maps output to Response DTO       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ Use Case Layer (`usecases/<action>_usecase.py`)        │
│ - Executes core business logic                         │
│ - Decorated with @Transactional for write operations   │
│ - Calls Output Ports (Interfaces), never ORM models    │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌───────────────────────────┐ ┌───────────────────────────┐
│ Domain Entities (`shared`)│ │ Output Ports (Interfaces) │
│ - Pure Pydantic models    │ │ - Abstract Base Classes   │
│ - Business rules / fields │ │ - Defines repo contracts  │
└───────────────────────────┘ └─────────────┬─────────────┘
                                            │
                                            ▼
┌────────────────────────────────────────────────────────┐
│ Infrastructure Layer (`infrastructure/persistence/`)    │
│ - Implements Output Ports                              │
│ - Injects SessionDep                                   │
│ - Maps between SQLModel ORM Model and Domain Entity    │
└────────────────────────────────────────────────────────┘
```

---

## 📦 Layer Implementations

### 1. Domain Entities (`src/modules/shared/domain/entities/`)
Pure Pydantic models representing business domain concepts. They **must not** contain SQLModel annotations, table definitions, or database metadata.

```python
# src/modules/shared/domain/entities/user_entity.py
from pydantic import BaseModel
import uuid

class UserEntity(BaseModel):
    id: uuid.UUID | None = None
    username: str
    email: str
    is_active: bool = True
```

### 2. ORM Table Models (`src/modules/shared/infrastructure/models/`)
SQLModel table models used exclusively by database repositories and Alembic migrations.

```python
# src/modules/shared/infrastructure/models/user_model.py
import uuid
from sqlmodel import SQLModel, Field

class UserModel(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str
    email: str
    is_active: bool = True
```

> [!IMPORTANT]
> Use cases must **never** import or instantiate SQLModel classes directly. All DB conversions happen strictly within repository classes.

### 3. Output Ports (`src/modules/<module>/ports/output/`)
Abstract interfaces defining repository methods needed by the use case.

```python
# src/modules/users/ports/output/user_repository.py
from abc import ABC, abstractmethod
from src.modules.shared.domain.entities import UserEntity

class IUserRepository(ABC):
    @abstractmethod
    def create(self, user: UserEntity) -> UserEntity:
        pass

    @abstractmethod
    def find_by_id(self, user_id: str) -> UserEntity | None:
        pass
```

### 4. Persistence Repositories (`src/modules/<module>/infrastructure/persistence/`)
Implements the interface, converts between `UserModel` (ORM) and `UserEntity` (Domain), and uses `self.session.flush()` during mutations.

```python
# src/modules/users/infrastructure/persistence/user_repository.py
from fastapi import Depends
from typing import Annotated
from src.modules.users.ports.output import IUserRepository
from src.modules.shared.domain.entities import UserEntity
from src.modules.shared.infrastructure.models import UserModel
from src.libs.database.session import SessionDep

class UserRepository(IUserRepository):
    def __init__(self, session: SessionDep):
        self.session = session

    def create(self, user: UserEntity) -> UserEntity:
        model = self.__to_model(user)
        self.session.add(model)
        self.session.flush()
        return self.__to_entity(model)

    def find_by_id(self, user_id: str) -> UserEntity | None:
        model = self.session.get(UserModel, user_id)
        if model is None:
            return None
        return self.__to_entity(model)

    def __to_entity(self, model: UserModel) -> UserEntity:
        return UserEntity(id=model.id, username=model.username, email=model.email, is_active=model.is_active)

    def __to_model(self, entity: UserEntity) -> UserModel:
        return UserModel(id=entity.id, username=entity.username, email=entity.email, is_active=entity.is_active)

IUserRepoDep = Annotated[IUserRepository, Depends(UserRepository)]
```

### 5. Use Cases (`src/modules/<module>/usecases/`)
Encapsulates a single business action. Injects repository dependency aliases and uses `@Transactional` on write methods.

```python
# src/modules/users/usecases/create_user_usecase.py
from typing import Annotated
from fastapi import Depends
from src.modules.users.ports.output import IUserRepoDep
from src.modules.shared.domain.entities import UserEntity
from src.modules.users.presenter.dtos import CreateUserRequestDto, CreateUserResponseDto
from src.libs.decorators.transactional_decorator import Transactional

class CreateUserUsecase:
    def __init__(self, user_repo: IUserRepoDep):
        self.user_repo = user_repo

    @Transactional
    async def execute(self, user_dto: CreateUserRequestDto) -> CreateUserResponseDto:
        user_entity = self.user_repo.create(user_dto.to_entity())
        return self.__to_response(user_entity)

    def __to_response(self, user_entity: UserEntity) -> CreateUserResponseDto:
        return CreateUserResponseDto(id=str(user_entity.id))

CreateUserUsecaseDep = Annotated[CreateUserUsecase, Depends(CreateUserUsecase)]
```

### 6. Presenter / Routers (`src/modules/<module>/presenter/`)
FastAPI APIRouter endpoint handlers.

```python
# src/modules/users/presenter/router.py
from fastapi import APIRouter, status
from src.modules.users.usecases import CreateUserUsecaseDep, GetUserUsecaseDep
from src.modules.users.presenter.dtos import (
    CreateUserRequestDto,
    CreateUserResponseDto,
    GetUserResponseDto,
)

user_router = APIRouter(prefix="/users", tags=["users"])

@user_router.post("", response_model=CreateUserResponseDto, status_code=status.HTTP_201_CREATED)
async def create_user(user: CreateUserRequestDto, usecase: CreateUserUsecaseDep) -> CreateUserResponseDto:
    return await usecase.execute(user)

@user_router.get("/{user_id}", response_model=GetUserResponseDto)
async def get_user(user_id: str, usecase: GetUserUsecaseDep) -> GetUserResponseDto:
    return await usecase.execute(user_id)
```
