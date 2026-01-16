from __future__ import annotations

from indexer_engine.app.config import settings
from indexer_engine.app.domain.ports.out import AnalyticsEvmEventsIndexer
from indexer_engine.app.application.services.index_analytics_evm_events_for_block_range import (
    BlockRange,
    index_analytics_evm_events_for_block_range,
)
from indexer_engine.app.infrastructure.factories.analytics_evm_events_indexer_factory import (
    analytics_evm_events_indexer_factory,
)
from indexer_engine.app.infrastructure.db.engine import create_app_async_engine
from indexer_engine.app.application.services.block_bounds import resolve_block_bounds_from_table


async def index_analytics_evm_events_task(
    *,
    chain_id: int,
    from_block: int | str,
    to_block: int | str,
    backend: str = "sqlalchemy",
) -> None:
    """
    Task: data indexing to analytics.evm_events for a given chain and block range.

    - takes data from staging.evm_event_logs,
    - enriches with event_name / event_signature,
    - writes to analytics.evm_events.
    """
    engine = create_app_async_engine()
    try:
        resolved_from_block, resolved_to_block = await resolve_block_bounds_from_table(
            engine=engine,
            chain_id=chain_id,
            from_block=from_block,
            to_block=to_block,
            source_table="staging.evm_event_logs",
        )

        indexer: AnalyticsEvmEventsIndexer = analytics_evm_events_indexer_factory(
            backend=backend,
            engine=engine,
        )

        await index_analytics_evm_events_for_block_range(
            indexer=indexer,
            chain_id=chain_id,
            block_range=BlockRange(
                from_block=resolved_from_block,
                to_block=resolved_to_block,
            ),
        )
    finally:
        await engine.dispose()
