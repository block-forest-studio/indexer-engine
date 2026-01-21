from __future__ import annotations

from indexer_engine.app.domain.ports.out import EvmEventLogsIndexer
from indexer_engine.app.infrastructure.factories.staging.evm_event_logs_indexer import evm_event_logs_indexer_factory
from indexer_engine.app.application.services.staging.index_evm_event_logs_for_block_range import (
    BlockRange,
    index_evm_event_logs_for_block_range,
)
from indexer_engine.app.application.services.analytics.block_bounds import resolve_block_bounds_from_table
from indexer_engine.app.infrastructure.db.engine import create_app_async_engine


async def index_evm_event_logs_task(
    *,
    chain_id: int,
    from_block: int | str,
    to_block: int | str,
    backend: str = "sqlalchemy",
) -> None:
    """
    Indexes EVM logs into staging.evm_event_logs for a given chain and block range.

    from_block / to_block can be:
    - int (a specific block number),
    - "earliest" (the first available block in raw.logs),
    - "latest" (the last available block in raw.logs).
    """
    engine = create_app_async_engine()
    try:
        resolved_from_block, resolved_to_block = await resolve_block_bounds_from_table(
            engine=engine,
            chain_id=chain_id,
            from_block=from_block,
            to_block=to_block,
            source_table="raw.logs",
        )

        indexer: EvmEventLogsIndexer = evm_event_logs_indexer_factory(
            backend=backend,
            engine=engine,
        )

        await index_evm_event_logs_for_block_range(
            indexer=indexer,
            chain_id=chain_id,
            block_range=BlockRange(
                from_block=resolved_from_block,
                to_block=resolved_to_block,
            ),
        )
    finally:
        await engine.dispose()
