from __future__ import annotations
from pathlib import Path

from indexer_engine.app.application.services.analytics.block_bounds import (
    resolve_block_bounds_from_table,
)
from indexer_engine.app.application.services.domain.index_uniswap_v4_wallet_swaps_for_block_range import (
    BlockRange,
    index_uniswap_v4_wallet_swaps_for_block_range,
)
from indexer_engine.app.domain.ports.out import UniswapV4WalletSwapsIndexer
from indexer_engine.app.infrastructure.db.engine import create_app_async_engine
from indexer_engine.app.infrastructure.factories.domain.uniswap_v4_wallet_swaps_indexer import (
    uniswap_v4_wallet_swaps_indexer_factory,
)


async def index_uniswap_v4_wallet_swaps_task(
    *,
    chain_id: int,
    from_block: int | str,
    to_block: int | str,
    backend: str = "sqlalchemy",
) -> None:
    """
    Task: data indexing to domain.uniswap_v4_wallet_swaps for a given chain and block range.

    - selects candidate events from analytics.evm_events (topic0 filter in adapter),
    - decodes Swap payload using ABI decoder,
    - writes to domain.uniswap_v4_wallet_swaps (idempotent via ON CONFLICT DO NOTHING).
    """
    engine = create_app_async_engine()
    try:
        resolved_from_block, resolved_to_block = await resolve_block_bounds_from_table(
            engine=engine,
            chain_id=chain_id,
            from_block=from_block,
            to_block=to_block,
            source_table="analytics.evm_events",
        )

        indexer: UniswapV4WalletSwapsIndexer = uniswap_v4_wallet_swaps_indexer_factory(
            backend=backend,
            engine=engine,
        )

        await index_uniswap_v4_wallet_swaps_for_block_range(
            indexer=indexer,
            chain_id=chain_id,
            block_range=BlockRange(
                from_block=resolved_from_block,
                to_block=resolved_to_block,
            ),
        )
    finally:
        await engine.dispose()
