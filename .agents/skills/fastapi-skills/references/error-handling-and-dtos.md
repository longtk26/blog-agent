# FastAPI Error Handling & DTOs Reference

This guide covers the custom exception hierarchy and Pydantic Request/Response DTO patterns used in the FastAPI application.

---

## 🛑 Custom Exception Hierarchy

All domain and business exceptions inherit from `BaseException` in `src/libs/exceptions/base_exception.py`, which subclasses FastAPI's `HTTPException`.

```python
# src/libs/exceptions/base_exception.py
from fastapi import HTTPException
from http import HTTPStatus
from typing import Any

class BaseException(HTTPException):
    def __init__(self, status_code: int, detail: Any):
        super().__init__(status_code=status_code, detail=detail)

class NotFoundException(BaseException):
    def __init__(self, detail: Any = "Resource not found"):
        super().__init__(status_code=HTTPStatus.NOT_FOUND, detail=detail)

class BadRequestException(BaseException):
    def __init__(self, detail: Any = "Bad request"):
        super().__init__(status_code=HTTPStatus.BAD_REQUEST, detail=detail)

class UnauthorizedException(BaseException):
    def __init__(self, detail: Any = "Unauthorized"):
        super().__init__(status_code=HTTPStatus.UNAUTHORIZED, detail=detail)

class ForbiddenException(BaseException):
    def __init__(self, detail: Any = "Forbidden"):
        super().__init__(status_code=HTTPStatus.FORBIDDEN, detail=detail)

class InternalServerErrorException(BaseException):
    def __init__(self, detail: Any = "Internal server error"):
        super().__init__(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=detail)
```

### Raising Exceptions in Business Logic

Raise descriptive exceptions in use cases or services rather than handling raw HTTP errors:

```python
# src/modules/users/usecases/get_user_usecase.py
from src.libs.exceptions import NotFoundException

class GetUserUsecase:
    def __init__(self, user_repo: IUserRepoDep):
        self.user_repo = user_repo

    async def execute(self, user_id: str) -> GetUserResponseDto:
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise NotFoundException(f"User with ID '{user_id}' not found")
        return GetUserResponseDto(
            id=str(user.id),
            username=user.username,
            email=user.email,
            is_active=user.is_active
        )
```

---

## 📝 Request and Response DTOs

DTOs live in `src/modules/<module>/presenter/dtos/`.

### Request DTO with `.to_entity()`
Request DTOs should encapsulate input fields, validation rules, and provide a converter method to create a Domain Entity:

```python
# src/modules/users/presenter/dtos/create_user_dto.py
from pydantic import BaseModel, EmailStr
from src.modules.shared.domain.entities import UserEntity

class CreateUserRequestDto(BaseModel):
    username: str
    email: EmailStr
    is_active: bool = True

    def to_entity(self) -> UserEntity:
        return UserEntity(
            username=self.username,
            email=self.email,
            is_active=self.isActive if hasattr(self, 'isActive') else self.is_active
        )

class CreateUserResponseDto(BaseModel):
    id: str
```

### Response DTO
Response DTOs define strictly what data is serialized and exposed over HTTP:

```python
# src/modules/users/presenter/dtos/get_user_dto.py
from pydantic import BaseModel

class GetUserResponseDto(BaseModel):
    id: str
    email: str
    username: str
    is_active: bool
```
