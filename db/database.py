"""
Async database engine and session management.

The async engine is created lazily so that importing this module (and Base)
does not require asyncpg to be installed — needed by the Streamlit auth
module which uses a separate sync engine.
"""

from contextlib import asynccontextmanager

from sqlalchemy import inspect, text
from sqlalchemy.orm import DeclarativeBase

from config.settings import get_settings


class Base(DeclarativeBase):
    pass


# Lazy async engine — only created when first accessed
_engine = None
_async_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy.ext.asyncio import create_async_engine

        from sqlalchemy.pool import NullPool, QueuePool

        settings = get_settings()
        kwargs = dict(echo=False)
        if settings.use_sqlite:
            # NullPool: new connection per request — always reads fresh data from disk.
            # StaticPool caused stale reads when the DB was written by another connection.
            kwargs["connect_args"] = {"check_same_thread": False}
            kwargs["poolclass"] = NullPool
        else:
            kwargs["pool_size"] = 20
            kwargs["max_overflow"] = 10
            kwargs["pool_pre_ping"] = True
        _engine = create_async_engine(settings.database_url, **kwargs)
    return _engine


def _get_session_factory():
    global _async_session_factory
    if _async_session_factory is None:
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

        _async_session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def get_session():
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db():
    """FastAPI dependency that yields an AsyncSession."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    async with _get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Compatibility shim for local/dev startups that call create_all directly
    # instead of running Alembic migrations against an existing database.
    await _ensure_legacy_trade_user_schema()
    # Seed static reference data (idempotent — skips existing rows)
    from scripts.seed_providers import seed as _seed_providers
    await _seed_providers()
    # Seed demo strategies so Quant Intelligence features are immediately visible
    from scripts.seed_demo_strategies import seed as _seed_demo_strategies
    await _seed_demo_strategies()


async def close_db():
    if _engine is not None:
        await _engine.dispose()


async def _ensure_legacy_trade_user_schema() -> None:
    async with _get_engine().begin() as conn:
        def _ensure(sync_conn) -> None:
            inspector = inspect(sync_conn)
            if "trades" not in inspector.get_table_names():
                return

            columns = {column["name"] for column in inspector.get_columns("trades")}
            if "user_id" not in columns:
                sync_conn.execute(text("ALTER TABLE trades ADD COLUMN user_id INTEGER"))

            sync_conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_trades_user_id ON trades (user_id)")
            )
            sync_conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_trades_user_mode_time "
                    "ON trades (user_id, mode, entry_time)"
                )
            )

        await conn.run_sync(_ensure)


# Import all models so Base.metadata includes them for Alembic and init_db
import db.models  # noqa: F401
import db.cerberus_models  # noqa: F401
