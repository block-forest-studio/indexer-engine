from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict

from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import UniswapV4PoolsIndexer
from indexer_engine.app.infrastructure.adapters.domain.uniswap_v4_pools_indexer import (
    SqlAlchemyUniswapV4PoolsIndexer,
)
from indexer_engine.app.infrastructure.decoders.uniswap_v4.initialize_decoder import (
    InitializeDecoder,
)

UniswapV4PoolsIndexerFactory = Callable[[AsyncEngine], UniswapV4PoolsIndexer]

_UNISWAP_V4_POOLS_INDEXER_REGISTRY: Dict[str, UniswapV4PoolsIndexerFactory] = {}

# -----------------------------------------------------------------------------
# Defaults for Uniswap v4 Initialize decoding
# -----------------------------------------------------------------------------
_DEFAULT_BATCH_SIZE = 10_000

# Resolve ABI path robustly (relative to repository/module, not current working dir)
_DEFAULT_ABI_PATH = (
    Path(__file__).resolve().parents[3]  # .../indexer_engine/app/infrastructure/factories
    / "registry"
    / "abi"
    / "PoolManager.json"
)


def _make_sqlalchemy_indexer(
    engine: AsyncEngine,
    *,
    abi_path: Path,
    event_name: str,
    batch_size: int,
) -> UniswapV4PoolsIndexer:
    """
    Wire dependencies for SQLAlchemy backend:
    - ABI-based Initialize decoder (Uniswap v4 PoolManager ABI)
    - SQL indexer filtering by decoder.topic0 and inserting decoded rows into domain.uniswap_v4_pools
    """
    decoder = InitializeDecoder(abi_path=abi_path, event_name=event_name)

    return SqlAlchemyUniswapV4PoolsIndexer(
        engine=engine,
        decoder=decoder,
        topic0_as_sql_filter=decoder.topic0,
        batch_size=batch_size,
    )


# Register backends
_UNISWAP_V4_POOLS_INDEXER_REGISTRY["sqlalchemy"] = lambda engine: _make_sqlalchemy_indexer(
    engine,
    abi_path=_DEFAULT_ABI_PATH,
    event_name="Initialize",
    batch_size=_DEFAULT_BATCH_SIZE,
)


def uniswap_v4_pools_indexer_factory(
    *,
    backend: str,
    engine: AsyncEngine,
) -> UniswapV4PoolsIndexer:
    """
    Create a Uniswap v4 pools indexer for the given backend.

    The factory wires:
    - ABI-based event decoder (loads PoolManager.json, computes topic0 for Initialize),
    - SQLAlchemy indexer adapter (filters by topic0, decodes payload, inserts to domain table).
    """
    try:
        factory = _UNISWAP_V4_POOLS_INDEXER_REGISTRY[backend]
    except KeyError:
        raise ValueError(f"Unsupported Uniswap v4 pools indexer backend: {backend!r}")

    return factory(engine)
