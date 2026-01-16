from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from indexer_engine.app.infrastructure.db.db_base import BaseDB


class AnalyticsBlocksDB(BaseDB):
    """
    Canonical analytics table for EVM blocks.

    Each row represents a single block on a given chain, including
    its canonical timestamp and basic gas / execution metadata.
    """

    __tablename__ = "blocks"
    __table_args__ = (
        # Natural primary key: unique block per chain
        PrimaryKeyConstraint("chain_id", "block_number"),
        # Common access pattern: filter by time for a given chain
        Index(
            "ix_analytics_blocks_chain_timestamp",
            "chain_id",
            "timestamp",
        ),
        # Lookup by block hash on a given chain
        Index(
            "ix_analytics_blocks_chain_hash",
            "chain_id",
            "block_hash",
        ),
        {"schema": "analytics"},
    )
    # -------------------------------------------------------------------------
    # Chain / identity
    # -------------------------------------------------------------------------
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    block_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    parent_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    # -------------------------------------------------------------------------
    # Time
    # -------------------------------------------------------------------------
    # Canonical block timestamp (UTC)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    # -------------------------------------------------------------------------
    # Gas / execution metadata
    # -------------------------------------------------------------------------
    # Base fee per gas (EIP-1559); may be NULL on older blocks / chains
    base_fee_per_gas: Mapped[Numeric | None] = mapped_column(
        Numeric(38, 0),
        nullable=True,
    )
    gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    gas_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Number of transactions in the block (optional)
    tx_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
