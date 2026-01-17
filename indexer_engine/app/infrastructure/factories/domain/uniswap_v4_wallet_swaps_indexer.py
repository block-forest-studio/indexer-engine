# from __future__ import annotations

# from sqlalchemy.ext.asyncio import AsyncEngine

# from indexer_engine.app.infrastructure.db.adapters.sqlalchemy_uniswap_v4_wallet_swaps_indexer import (
#     SqlAlchemyUniswapV4WalletSwapsIndexer,
#     UniswapV4SwapDecoder,
# )


# def uniswap_v4_wallet_swaps_indexer_factory(
#     *,
#     backend: str,
#     engine: AsyncEngine,
#     decoder: UniswapV4SwapDecoder,
#     swap_topic0: bytes,
# ) -> SqlAlchemyUniswapV4WalletSwapsIndexer:
#     if backend != "sqlalchemy":
#         raise ValueError(f"Unsupported backend: {backend!r}")

#     return SqlAlchemyUniswapV4WalletSwapsIndexer(
#         engine,
#         decoder=decoder,
#         swap_topic0=swap_topic0,
#     )
