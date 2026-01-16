from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    Numeric,
    Text,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from indexer_engine.app.infrastructure.db.db_base import BaseDB


class AnalyticsEvmEventsDB(BaseDB):
    """
    Canonical analytics table for decoded EVM events.

    Each row represents a single log entry emitted by a contract, enriched with
    basic transaction context and decoded event identity (name + signature).
    """

    __tablename__ = "evm_events"
    __table_args__ = (
        PrimaryKeyConstraint("chain_id", "transaction_hash", "log_index"),
        Index(
            "ix_analytics_events_chain_contract_event_block",
            "chain_id",
            "contract_address",
            "event_name",
            "block_number",
        ),
        Index(
            "ix_analytics_events_chain_tx",
            "chain_id",
            "transaction_hash",
        ),

        {"schema": "analytics"},
    )
    # -------------------------------------------------------------------------
    # Chain
    # -------------------------------------------------------------------------
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # -------------------------------------------------------------------------
    # Transaction
    # -------------------------------------------------------------------------
    transaction_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)
    log_index: Mapped[int] = mapped_column(Integer, nullable=False)

    tx_gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    tx_effective_gas_price: Mapped[Numeric | None] = mapped_column(Numeric, nullable=True)
    tx_value: Mapped[Numeric] = mapped_column(Numeric, nullable=False)

    tx_from_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    tx_to_address: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    # -------------------------------------------------------------------------
    # Raw event payload (topics + data)
    # -------------------------------------------------------------------------
    topic0: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)  # ZMIANA!
    topic1: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)  # ZMIANA!
    topic2: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)  # ZMIANA!
    topic3: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)  # ZMIANA!
    data: Mapped[bytes] = mapped_column(BYTEA, nullable=False)          # ZMIANA!
    # -------------------------------------------------------------------------
    # Contract and event
    # -------------------------------------------------------------------------
    contract_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    event_signature: Mapped[str] = mapped_column(Text, nullable=False)
