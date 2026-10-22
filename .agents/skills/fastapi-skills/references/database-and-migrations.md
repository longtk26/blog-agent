# FastAPI Database & Migrations Reference

This guide covers database configuration, SQLModel entity models, and the Alembic migration workflow.

---

## 🗄️ Database Setup & Configuration

Database settings are configured via `pydantic-settings` in `src/configs/config.py`:

```python
# src/configs/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "FastAPI App"
    port: int = 8000
    db_url: str = "postgresql://user:password@localhost:5432/dbname"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

config = Settings()
```

---

## 📐 SQLModel Table Models

SQLModel models must live in `src/modules/shared/infrastructure/models/`. Every model must specify `table=True` and `__tablename__`.

```python
# src/modules/shared/infrastructure/models/user_model.py
import uuid
from sqlmodel import SQLModel, Field

class UserModel(SQLModel, table=True):
    __tablename__ = "users"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    username: str = Field(index=True, nullable=False)
    email: str = Field(unique=True, index=True, nullable=False)
    is_active: bool = Field(default=True)
```

---

## 🔄 Alembic Model Registration

For Alembic to detect new models when autogenerating migrations, all models must be imported in `src/modules/__init__.py`:

```python
# src/modules/__init__.py
from src.modules.shared.infrastructure.models.user_model import UserModel
from src.modules.shared.infrastructure.models.product_model import ProductModel

__all__ = ["UserModel", "ProductModel"]
```

`alembic/env.py` references `SQLModel.metadata` where all imported models register themselves.

---

## 🛠️ Migration Commands

Use the provided Makefile targets to manage database migrations:

```bash
# 1. Create a new migration script from model changes
make newmg name="create_users_table"

# 2. Review the generated file in alembic/versions/

# 3. Apply all pending migrations to the database
make mghead

# 4. Rollback the last applied migration
make mgdown
```
