from __future__ import annotations

from dataclasses import dataclass

from indexer_engine.app.domain.ports.out import (
    UniswapV4PoolsIndexer,
)


@dataclass(frozen=True)
class BlockRange:
    from_block: int
    to_block: int

    def validate(self) -> None:
        if self.from_block < 0 or self.to_block < 0:
            raise ValueError("Block numbers must be non-negative")
        if self.from_block > self.to_block:
            raise ValueError("from_block must be <= to_block")


async def index_uniswap_v4_pools_for_block_range(
    *,
    indexer: UniswapV4PoolsIndexer,
    chain_id: int,
    block_range: BlockRange,
) -> None:
    block_range.validate()
    await indexer.index_pools_for_block_range(
        chain_id=chain_id,
        from_block=block_range.from_block,
        to_block=block_range.to_block,
    )
