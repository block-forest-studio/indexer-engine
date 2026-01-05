from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import AnalyticsEvmEventsIndexer
from indexer_engine.app.infrastructure.adapters.analytics_evm_events_indexer import (
    SqlAlchemyAnalyticsEvmEventsIndexer,
)

AnalyticsEvmEventsIndexerFactory = Callable[[AsyncEngine], AnalyticsEvmEventsIndexer]

_ANALYTICS_EVM_EVENTS_INDEXER_REGISTRY: Dict[str, AnalyticsEvmEventsIndexerFactory] = {
    "sqlalchemy": lambda engine: SqlAlchemyAnalyticsEvmEventsIndexer(engine),
}


def analytics_evm_events_indexer_factory(
    *,
    backend: str,
    engine: AsyncEngine,
) -> AnalyticsEvmEventsIndexer:
    try:
        factory = _ANALYTICS_EVM_EVENTS_INDEXER_REGISTRY[backend]
    except KeyError:
        raise ValueError(f"Unsupported analytics EVM events indexer backend: {backend!r}")
    return factory(engine)
