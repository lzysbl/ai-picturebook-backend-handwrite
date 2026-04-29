"""Database bootstrap and lightweight schema compatibility fixes."""

from __future__ import annotations

from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import Book, BookImage, Story, User  # noqa: F401


async def init_db() -> None:
    """Create all tables and backfill new auth columns for existing databases."""

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_user_auth_columns)


def _ensure_user_auth_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "users" not in set(inspector.get_table_names()):
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    indexes = {index["name"] for index in inspector.get_indexes("users")}
    dialect = sync_conn.dialect.name

    if "email" not in columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL"))
    if "reset_password_token_hash" not in columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN reset_password_token_hash VARCHAR(255) NULL"))
    if "reset_password_expires_at" not in columns:
        sync_conn.execute(text("ALTER TABLE users ADD COLUMN reset_password_expires_at DATETIME NULL"))

    if "ix_users_email_unique" not in indexes and dialect != "sqlite":
        sync_conn.execute(text("CREATE UNIQUE INDEX ix_users_email_unique ON users (email)"))
