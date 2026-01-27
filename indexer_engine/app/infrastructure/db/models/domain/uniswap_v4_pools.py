from __future__ import annotations

from datetime import datetime

from indexer_engine.app.infrastructure.db.db_base import BaseDB
from sqlalchemy import (
    BigInteger,
    Integer,
    Index,
    PrimaryKeyConstraint,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import BYTEA


class UniswapV4PoolsDB(BaseDB):
    """
    Pool registry for Uniswap v4.

    One row = one pool_id initialized in PoolManager (from Initialize event).
    """

    __tablename__ = "uniswap_v4_pools"
    __table_args__ = (
        PrimaryKeyConstraint("chain_id", "pool_id"),
        Index(
            "ix_uni_v4_pools_chain_manager",
            "chain_id",
            "pool_manager",
        ),
        Index(
            "ix_uni_v4_pools_chain_tokens",
            "chain_id",
            "token0_address",
            "token1_address",
        ),
        {"schema": "domain"},
    )

    # Identity
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    pool_id: Mapped[bytes] = mapped_column(BYTEA, nullable=False)  # bytes32

    # Protocol
    pool_manager: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    # Pool config (minimum required for swaps enrichment)
    token0_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)  # currency0
    token1_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)  # currency1

    # Optional: keep these if you already decode them from Initialize
    fee: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tick_spacing: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hooks: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    # Creation metadata (for debugging/time queries)
    created_block: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
