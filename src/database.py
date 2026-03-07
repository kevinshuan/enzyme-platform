from collections.abc import AsyncGenerator

from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import AsyncAdaptedQueuePool

from fastapi import Request


class Base(DeclarativeBase):
    pass


def _as_async_url(url: str) -> str:
    """Ensure psycopg driver and async format."""
    db_url = make_url(url)
    if (
        db_url.drivername.startswith("postgresql")
        and "+psycopg" not in db_url.drivername
    ):
        db_url = db_url.set(drivername="postgresql+psycopg")
    return db_url.render_as_string(hide_password=False)


def _is_local(db_url) -> bool:
    """Check local/dev hosts, including common Docker names."""
    host = db_url.host or ""
    return host in {"localhost", "127.0.0.1", "db", "postgres"}


def _has_explicit_ssl(db_url) -> bool:
    """Check if SSL parameters are already present."""
    return any(
        key in (db_url.query or {})
        for key in ("ssl", "sslmode", "sslrootcert", "sslcert", "sslkey")
    )


def create_engine_and_sessionmaker(
    url: str,
    *,
    pool_size: int,
    max_overflow: int,
    pool_timeout: int,
    pool_recycle: int,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    db_url = make_url(_as_async_url(url))

    if not _is_local(db_url) and not _has_explicit_ssl(db_url):
        query_params = dict(db_url.query)
        query_params["sslmode"] = "require"
        db_url = db_url.set(query=query_params)

    final_async_url = db_url.render_as_string(hide_password=False)
    connect_args = {"prepare_threshold": 0}

    pool_kwargs = {
        "poolclass": AsyncAdaptedQueuePool,
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": pool_recycle,
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }

    engine = create_async_engine(final_async_url, **pool_kwargs)
    session_factory = async_sessionmaker(
        bind=engine, expire_on_commit=False, class_=AsyncSession
    )
    return engine, session_factory


def _require_sessionmaker(
    request: Request,
) -> async_sessionmaker[AsyncSession]:
    sessionmaker = getattr(request.app.state, "sessionmaker", None)
    if sessionmaker is None:
        raise RuntimeError(
            "Database sessionmaker is not initialized. "
            "Ensure app lifespan startup has completed."
        )
    return sessionmaker


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: provide a DB session from app state."""
    sessionmaker = _require_sessionmaker(request)
    async with sessionmaker() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
