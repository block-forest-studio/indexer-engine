from __future__ import annotations

from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import EvmEventLogsIndexer
from indexer_engine.app.infrastructure.adapters.evm_event_logs_indexer import (
    SqlAlchemyEvmEventLogsIndexer,
)


EvmEventLogsIndexerFactory = Callable[[AsyncEngine], EvmEventLogsIndexer]

_EVM_EVENT_LOGS_INDEXER_REGISTRY: Dict[str, EvmEventLogsIndexerFactory] = {
    "sqlalchemy": lambda engine: SqlAlchemyEvmEventLogsIndexer(engine=engine),
    # in future:
    # "fake": lambda engine: FakeEvmEventLogsIndexer(),
    # "raw_sql": lambda engine: RawSqlEvmEventLogsIndexer(engine=engine),
}


def evm_event_logs_indexer_factory(
    backend: str,
    engine: AsyncEngine,
) -> EvmEventLogsIndexer:
    try:
        factory = _EVM_EVENT_LOGS_INDEXER_REGISTRY[backend]
    except KeyError:
        raise ValueError(f"Unsupported EVM event logs indexer backend: {backend!r}")
    return factory(engine)
