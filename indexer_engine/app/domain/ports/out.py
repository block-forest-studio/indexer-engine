from __future__ import annotations

from typing import Protocol


class EvmEventLogsIndexer(Protocol):
    """
    Port for indexing EVM event logs into the staging layer.

    Implementations are responsible for loading data from raw.* tables
    into staging.evm_event_logs in an idempotent, set-based way.
    """

    async def index_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        ...


class AnalyticsEvmEventsIndexer(Protocol):
    """
    Port for indexing normalized EVM events into the analytics layer.

    Implementations are responsible for transforming rows from
    staging.evm_event_logs into analytics.evm_events in an idempotent,
    set-based way.

    The analytics layer represents a curated, query-optimized view of on-chain
    activity.
    """
    async def index_events_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        ...


class UniswapV4WalletSwapsIndexer(Protocol):
    """
    Port for indexing Uniswap v4 wallet swap projections into the domain layer.
    """
    async def index_swaps_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None: ...
