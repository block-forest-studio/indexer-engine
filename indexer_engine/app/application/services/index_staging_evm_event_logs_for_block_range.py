from __future__ import annotations

from dataclasses import dataclass

from indexer_engine.app.domain.ports.out import EvmEventLogsIndexer


@dataclass(frozen=True)
class BlockRange:
    from_block: int
    to_block: int

    def validate(self) -> None:
        if self.from_block < 0 or self.to_block < 0:
            raise ValueError("Block numbers must be non-negative")
        if self.from_block > self.to_block:
            raise ValueError("from_block must be <= to_block")


async def index_staging_evm_event_logs_for_block_range(
    *,
    indexer: EvmEventLogsIndexer,
    chain_id: int,
    block_range: BlockRange,
) -> None:
    """
    Application-level use case for indexing EVM event logs into staging.

    Orchestrates validation and calls the underlying indexer port.
    """
    block_range.validate()
    await indexer.index_block_range(
        chain_id=chain_id,
        from_block=block_range.from_block,
        to_block=block_range.to_block,
    )
