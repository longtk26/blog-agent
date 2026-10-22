from typing import Annotated

from fastapi import Depends
from sqlalchemy import text
from sqlmodel import Session, create_engine, SQLModel
from src.configs import config


def to_sqlalchemy_url(db_url: str) -> str:
    """Use the psycopg (v3) driver for SQLAlchemy; LangGraph's checkpointer needs the plain libpq URL."""
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if db_url.startswith(prefix):
            return "postgresql+psycopg://" + db_url[len(prefix):]
    return db_url


def to_libpq_url(db_url: str) -> str:
    return db_url.replace("postgresql+psycopg://", "postgresql://", 1)


class DBSessionManager:
    def __init__(self):
        self.engine = self.create_db_engine(config.db_url)

    def create_db_engine(self, db_url: str):
        return create_engine(to_sqlalchemy_url(db_url), pool_pre_ping=True)

    def create_db_and_tables(self):
        SQLModel.metadata.create_all(self.engine)

    def get_session(self):
        with Session(self.engine) as session:
            yield session

    def ping(self) -> bool:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


db_session_manager = DBSessionManager()

SessionDep = Annotated[Session, Depends(db_session_manager.get_session)]
