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
