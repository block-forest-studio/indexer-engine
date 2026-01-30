from __future__ import annotations

from indexer_engine.app.application.services.domain.index_tokens import index_tokens
from indexer_engine.app.domain.ports.out import TokensIndexer
from indexer_engine.app.infrastructure.db.engine import create_app_async_engine
from indexer_engine.app.infrastructure.factories.domain.erc20_tokens_factory import (
    erc20_tokens_indexer_factory,
)


async def erc20_tokens_task(
    *,
    chain_id: int,
    limit: int | None = None,
    backend: str = "sqlalchemy",
) -> None:
    """
    Task: fill domain.tokens for a given chain.

    - discovers token addresses from domain.uniswap_v4_pools (token0/token1),
    - fetches ERC-20 metadata via eth_call (symbol/decimals/name),
    - upserts into domain.tokens.
    """
    engine = create_app_async_engine()
    try:
        indexer: TokensIndexer = erc20_tokens_indexer_factory(
            backend=backend,
            engine=engine,
            chain_id=chain_id,
        )

        await index_tokens(
            indexer=indexer,
            chain_id=chain_id, 
            limit=limit,
        )
    finally:
        await engine.dispose()
