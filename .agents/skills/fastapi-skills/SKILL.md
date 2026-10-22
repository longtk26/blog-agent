---
name: fastapi-skills
description: Comprehensive guide for building FastAPI backend applications. Covers project bootstrap from template repo branch (feat/fastapi), module-based Hexagonal (Clean) Architecture, SQLModel ORM, Alembic migrations, custom Dependency Injection (type alias Dep pattern), method-level @Transactional decorator, custom BaseException hierarchy, DTO validation, rate limiting, structured logging, and strict separation between Domain Entities and ORM Models.
---

# FastAPI Backend Development Skill Guide

This skill guides agents when creating, bootstrapping, refactoring, or reviewing backend applications built with **FastAPI** in this project.

---

## ⚡ Project Initialization & Branch Cloning Guide

To start a new FastAPI backend project without writing boilerplate code from scratch, **always clone the template branch directly**:

```bash
# 1. Clone the dedicated FastAPI branch from template repo
git clone -b feat/fastapi --single-branch https://github.com/longtk26/template-frameworks.git <project_name>

# 2. Enter project directory & initialize fresh git repository
cd <project_name>
rm -rf .git
git init

# 3. Configure environment variables
cp .env.ex .env

# 4. Install dependencies (using virtual environment)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Apply migrations and run dev server
make mghead
make run
```

---

## 🛡️ Mandatory Core Capabilities & Verification Requirements

Every FastAPI backend created or maintained must verify and ensure the following **6 Core Pillars**:

1. **DTO Validation**:
   - Every request payload is modeled with Pydantic `BaseModel` in `modules/<module>/presenter/dtos/`.
   - Request DTOs define a `.to_entity()` converter method.
   - FastAPI automatically enforces type validation, query constraints, and body schemas.
2. **Rate Limiting**:
   - Protect API endpoints against brute force and abuse using rate limiting middleware (e.g. `slowapi` or custom in-memory token bucket).
3. **Transaction Handling**:
   - Write operations in use cases must be decorated with `@Transactional` (`src/libs/decorators/transactional_decorator.py`).
   - Repositories inject `SessionDep` and call `self.session.flush()` during mutations.
   - The transaction commits on method return and rolls back automatically if an exception is raised.
4. **Database Migrations (SQL)**:
   - Database schema managed via Alembic.
   - All SQLModel tables are imported into `src/modules/__init__.py`.
   - Migrations executed via `make newmg name="<description>"`, `make mghead`, and `make mgdown`.
5. **Centralized Error Handling**:
   - Business exceptions inherit from `BaseException` (`NotFoundException`, `BadRequestException`, `UnauthorizedException`, `ForbiddenException`, `InternalServerErrorException`) in `src/libs/exceptions/base_exception.py`.
   - Never raise unhandled raw `HTTPException` inside use cases.
6. **Structured Logging**:
   - Application logger configured in `src/configs/logger.py`.
   - Log critical operations, transaction states, and external API requests with contextual metadata.

---

## 🧭 Modular Reference Guides

For deep-dive explanations and code implementations, read the specialized reference documents:

| Topic / Task | Reference Guide | Summary / Focus |
|---|---|---|
| **Architecture & Structure** | [references/architecture-and-structure.md](references/architecture-and-structure.md) | Module directory structure (`ports/`, `usecases/`, `infrastructure/`, `presenter/`, `shared/`), layer separation |
| **Dependency Injection** | [references/dependency-injection.md](references/dependency-injection.md) | `I<Name>RepoDep` and `<Action>UsecaseDep` type aliases with `Annotated[..., Depends(...)]` |
| **Database & Migrations** | [references/database-and-migrations.md](references/database-and-migrations.md) | SQLModel models, `DBSessionManager`, `SessionDep`, Alembic migration workflow (`make newmg`, `make mghead`) |
| **Transaction Management** | [references/transactions.md](references/transactions.md) | `@Transactional` method-level decorator, session inspection, auto-commit and rollback |
| **Error Handling & DTOs** | [references/error-handling-and-dtos.md](references/error-handling-and-dtos.md) | Custom `BaseException` classes, Pydantic Request/Response DTOs with `.to_entity()` |

---

## ⚡ Core Rules Summary

1. **Hexagonal / Clean Layering**:
   - **Domain Entities** (`modules/shared/domain/entities/<name>_entity.py`): Pure Pydantic `BaseModel` without any ORM annotations.
   - **ORM Models** (`modules/shared/infrastructure/models/<name>_model.py`): Pure SQLModel classes (`SQLModel, table=True`). Only repositories may import or touch ORM models.
   - **Use Cases** (`modules/<module>/usecases/<action>_usecase.py`): Pure business logic. Must depend ONLY on output port interfaces (`I<Name>Repository`), never concrete repositories or ORM models.
   - **Presenters / Routers** (`modules/<module>/presenter/router.py`): FastAPI APIRouter handlers. Injects use cases, receives Request DTOs, returns Response DTOs.
2. **Dependency Injection**:
   - Define concrete-to-interface DI bindings as type aliases using `Annotated[Interface, Depends(Concrete)]`.
   - Repositories export `I<Name>RepoDep`.
   - Use cases export `<Action>UsecaseDep = Annotated[<Action>Usecase, Depends(<Action>Usecase)]`.
   - Controllers/routers inject `<Action>UsecaseDep`.
3. **Database & Transactions**:
   - Write operations in use cases must be decorated with `@Transactional`.
   - Repositories inject `SessionDep` and run operations on `self.session` using `self.session.flush()` during create/update so IDs generate without committing prematurely.
   - The `@Transactional` decorator commits the session upon successful execution and rolls back upon uncaught exceptions.
4. **Error Handling**:
   - Use custom exceptions derived from `BaseException` (e.g. `NotFoundException`, `BadRequestException`, `ForbiddenException`, `UnauthorizedException`) from `src/libs/exceptions/base_exception.py`.
   - Do NOT throw raw `HTTPException` inside use cases.
5. **Central Router Registry**:
   - All feature routers must be registered in `src/routers.py`.
   - All ORM models must be imported in `src/modules/__init__.py` so Alembic can discover them for migrations.

---

## 📁 Project File Structure

```text
src/
├── main.py                          # App entry point (FastAPI instance, lifespan, router inclusion)
├── routers.py                       # Central router registry
├── configs/
│   ├── config.py                    # Pydantic Settings singleton (reads .env)
│   └── logger.py                    # Structured logging setup
│
├── modules/
│   ├── __init__.py                  # Imports all ORM models for Alembic autogenerate
│   ├── shared/
│   │   ├── domain/
│   │   │   ├── entities/            # Pure Pydantic domain entities (no ORM annotations)
│   │   │   │   └── user_entity.py
│   │   │   └── value-objects/       # Domain value objects
│   │   └── infrastructure/
│   │       └── models/              # SQLModel ORM table classes
│   │           └── user_model.py
│   │
│   ├── health/                      # Health check module
│   │   ├── ports/input/
│   │   ├── usecases/
│   │   │   └── health_check_usecase.py
│   │   └── presenter/
│   │       ├── router.py
│   │       └── dtos/
│   │
│   └── <feature_module>/            # Feature module (e.g., users, orders)
│       ├── ports/
│       │   ├── input/               # Use case interfaces (optional)
│       │   └── output/              # Repository interfaces
│       │       └── <feature>_repository.py
│       ├── usecases/                # Business logic use cases + DI type aliases
│       │   ├── create_<feature>_usecase.py
│       │   └── get_<feature>_usecase.py
│       ├── infrastructure/
│       │   ├── persistence/         # Repository implementations + I<Feature>RepoDep
│       │   │   └── <feature>_repository.py
│       │   └── adapters/            # Third-party integrations
│       └── presenter/
│           ├── router.py            # FastAPI router
│           └── dtos/                # Request & Response Pydantic models
│               ├── create_<feature>_dto.py
│               └── get_<feature>_dto.py
│
└── libs/
    ├── database/
    │   └── session.py               # DBSessionManager and SessionDep
    ├── repository/
    │   └── base_repository.py       # Base repository helpers
    ├── exceptions/
    │   ├── base_exception.py        # BaseException, NotFoundException, etc.
    │   └── error_codes.py           # Application error codes
    └── decorators/
        └── transactional_decorator.py # @Transactional decorator
```

---

## 🛠️ Step-by-Step: Adding a New Feature Module

When creating a new feature module (e.g. `products`):

1. **Define Domain Entity**:
   - Create `src/modules/shared/domain/entities/product_entity.py` using pure Pydantic `BaseModel`.
2. **Define SQLModel ORM Model**:
   - Create `src/modules/shared/infrastructure/models/product_model.py` inheriting `SQLModel, table=True`.
   - Export it in `src/modules/__init__.py`.
   - Generate and apply Alembic migration: `make newmg name="create_products_table"` then `make mghead`.
3. **Define Output Port (Repository Interface)**:
   - Create `src/modules/products/ports/output/product_repository.py` with abstract class `IProductRepository(ABC)`.
4. **Implement Concrete Repository**:
   - Create `src/modules/products/infrastructure/persistence/product_repository.py`.
   - Inject `SessionDep`, implement mappings (`__to_entity`, `__to_model`), and declare `IProductRepoDep = Annotated[IProductRepository, Depends(ProductRepository)]`.
5. **Create DTOs**:
   - Create `src/modules/products/presenter/dtos/create_product_dto.py` with `to_entity()` method.
   - Create response DTOs.
6. **Implement Use Case**:
   - Create `src/modules/products/usecases/create_product_usecase.py`.
   - Inject `IProductRepoDep`, apply `@Transactional` to mutation methods, and define `CreateProductUsecaseDep`.
7. **Create Presenter / Router**:
   - Create `src/modules/products/presenter/router.py` with `product_router = APIRouter(prefix="/products", tags=["products"])`.
   - Inject `CreateProductUsecaseDep` into route handlers.
8. **Register Router**:
   - In `src/routers.py`, import `product_router` and add `router.include_router(product_router)`.

---

## ✅ PR & Review Checklist (6 Pillars Verified)

Before finishing tasks or opening a PR, verify:

- [ ] **Bootstrap**: Project bootstrapped from `feat/fastapi` template branch.
- [ ] **1. DTO Validation**: All request endpoints accept Pydantic DTOs with strict validation and `to_entity()` mapper methods.
- [ ] **2. Rate Limiting**: Rate limiting configured or attached to sensitive routes.
- [ ] **3. Transactions**: All write operations in use cases decorated with `@Transactional`; repositories call `flush()`.
- [ ] **4. Migrations**: SQLModel tables exported in `src/modules/__init__.py`; migrations generated and applied via Alembic (`make mghead`).
- [ ] **5. Error Handling**: Domain and HTTP errors use `BaseException` subclasses from `base_exception.py`.
- [ ] **6. Logger**: Structured logger initialized in `src/configs/logger.py` and used for logging errors and transaction events.
- [ ] **Layer Boundaries**: Domain Entities in `shared/domain/entities/` are pure Pydantic; Use cases never import SQLModel ORM models.
- [ ] **Dependency Injection**: Repositories export `I<Name>RepoDep`; Use cases export `<Action>UsecaseDep`.
- [ ] **Router Registration**: New routers registered in `src/routers.py`.
