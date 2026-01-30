from __future__ import annotations

from indexer_engine.app.domain.ports.out import TokensIndexer


async def index_tokens(
    *,
    indexer: TokensIndexer,
    chain_id: int,
    limit: int | None = None,
) -> None:
    if chain_id <= 0:
        raise ValueError("chain_id must be positive")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive when provided")

    await indexer.index_tokens(chain_id=chain_id, limit=limit)
