from __future__ import annotations

from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncEngine
from web3 import AsyncWeb3
from web3 import AsyncHTTPProvider

from indexer_engine.app.config import settings
from indexer_engine.app.domain.ports.out import TokensIndexer
from indexer_engine.app.infrastructure.adapters.domain.erc20_tokens_indexer import (
    SqlAlchemyTokensIndexer,
)
from indexer_engine.app.infrastructure.fetchers.erc20_tokens_fetcher import (
    Web3Erc20TokenMetadataFetcher,
)

TokensIndexerFactory = Callable[[AsyncEngine, int], TokensIndexer]

_TOKENS_INDEXER_REGISTRY: Dict[str, TokensIndexerFactory] = {}

_DEFAULT_BATCH_SIZE = 500


def _make_sqlalchemy_indexer(
    engine: AsyncEngine,
    *,
    chain_id: int,
    batch_size: int,
) -> TokensIndexer:
    """
    Wire dependencies for SQLAlchemy backend:
    - AsyncWeb3 provider (per-chain RPC URL)
    - ERC-20 metadata fetcher (symbol/decimals/name via eth_call)
    - SQLAlchemy indexer adapter (discovers tokens from pools and upserts into domain.tokens)
    """
    rpc_url = settings.rpc_url(chain_id)
    w3 = AsyncWeb3(
        AsyncHTTPProvider(
            rpc_url,
            request_kwargs={"timeout": 30},
        )
    )

    fetcher = Web3Erc20TokenMetadataFetcher(w3=w3)

    return SqlAlchemyTokensIndexer(
        engine=engine,
        fetcher=fetcher,
        batch_size=batch_size,
    )


# Register backends
_TOKENS_INDEXER_REGISTRY["sqlalchemy"] = lambda engine, chain_id: _make_sqlalchemy_indexer(
    engine,
    chain_id=chain_id,
    batch_size=_DEFAULT_BATCH_SIZE,
)


def erc20_tokens_indexer_factory(
    *,
    backend: str,
    engine: AsyncEngine,
    chain_id: int,
) -> TokensIndexer:
    """
    Create a tokens metadata indexer for the given backend.

    The factory wires:
    - web3 Async provider per chain,
    - ERC-20 metadata fetcher,
    - SQLAlchemy adapter that discovers missing tokens from domain.uniswap_v4_pools and upserts domain.tokens.
    """
    try:
        factory = _TOKENS_INDEXER_REGISTRY[backend]
    except KeyError:
        raise ValueError(f"Unsupported tokens indexer backend: {backend!r}")

    return factory(engine, chain_id)
