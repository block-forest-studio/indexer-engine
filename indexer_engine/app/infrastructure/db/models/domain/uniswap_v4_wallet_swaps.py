from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Integer,
    Numeric,
    Index,
    PrimaryKeyConstraint,
    DateTime,
    Text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from indexer_engine.app.infrastructure.db.db_base import BaseDB


class UniswapV4WalletSwapsDB(BaseDB):
    """
    Wallet-scoped swap projection for Uniswap v4.

    One row = one swap event observed on-chain and attributed to a wallet.
    This is an API-facing projection (serving model), built deterministically
    from analytics.evm_events (+ analytics.blocks for time filtering in queries).

    Idempotency:
      - PK matches the canonical event identity: (chain_id, transaction_hash, log_index)
    """

    __tablename__ = "uniswap_v4_wallet_swaps"
    __table_args__ = (
        PrimaryKeyConstraint("chain_id", "transaction_hash", "log_index"),
        # Fast wallet query + deterministic ordering (cursor pagination)
        Index(
            "ix_uni_v4_swaps_chain_wallet_order",
            "chain_id",
            "wallet_address",
            "block_number",
            "transaction_index",
            "log_index",
        ),
        # Optional: filter by pool_id in analytics/use-cases
        Index(
            "ix_uni_v4_swaps_chain_pool_order",
            "chain_id",
            "pool_id",
            "block_number",
            "transaction_index",
            "log_index",
        ),
        # Drill-down by tx hash
        Index(
            "ix_uni_v4_swaps_chain_tx",
            "chain_id",
            "transaction_hash",
        ),

        # Fast wallet timeline queries (most common API pattern)
        Index(
            "ix_uni_v4_swaps_wallet_time",
            "wallet_address",
            "block_timestamp",
        ),


        {"schema": "domain"},
    )

    # -------------------------------------------------------------------------
    # Identity / ordering (copied from analytics canonical event identity)
    # -------------------------------------------------------------------------
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    block_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    transaction_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    log_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # -------------------------------------------------------------------------
    # Wallet attribution (API dimension)
    # -------------------------------------------------------------------------
    wallet_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    # -------------------------------------------------------------------------
    # Protocol-specific identifiers
    # -------------------------------------------------------------------------
    pool_manager: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    pool_id: Mapped[bytes] = mapped_column(BYTEA, nullable=False)  # bytes32

    # Parties (if present in ABI/event args; otherwise can be filled later)
    sender: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    # -------------------------------------------------------------------------
    # Amounts (Uniswap-style: typically signed int256)
    # Use Numeric to safely store int256 range.
    # -------------------------------------------------------------------------
    amount0: Mapped[Numeric] = mapped_column(Numeric, nullable=False)
    amount1: Mapped[Numeric] = mapped_column(Numeric, nullable=False)

    # -------------------------------------------------------------------------
    # Optional swap state fields (include if present in v4 ABI)
    # -------------------------------------------------------------------------
    sqrt_price_x96: Mapped[Numeric | None] = mapped_column(Numeric, nullable=True)
    liquidity: Mapped[Numeric | None] = mapped_column(Numeric, nullable=True)
    tick: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # -------------------------------------------------------------------------
    # Optional traceability/debug fields
    # -------------------------------------------------------------------------
    event_signature: Mapped[str | None] = mapped_column(nullable=True)  # Text implied by dialect
