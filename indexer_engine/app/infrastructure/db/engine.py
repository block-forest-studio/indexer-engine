from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from indexer_engine.app.config import settings


def create_app_async_engine(*, echo: bool = False) -> AsyncEngine:
    """
    Factory for AsyncEngine used by background tasks / indexers.

    Centralizing engine creation keeps connection handling consistent
    across tasks and makes it easier to tweak pool settings in one place.
    """
    return create_async_engine(
        settings.database_url,  # postgresql+asyncpg://...
        echo=echo,
        pool_pre_ping=True,
    )
