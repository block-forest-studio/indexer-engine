from __future__ import annotations


from sqlalchemy import (
    BigInteger,
    Integer,
    SmallInteger,
    Numeric,
    Index,
    PrimaryKeyConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import BYTEA

from indexer_engine.app.infrastructure.db.db_base import BaseDB


class EvmEventLogsDB(BaseDB):
    """
    Canonical staging table for EVM event logs.

    Each row represents a single EVM log entry emitted by a smart contract,
    uniquely identified within the canonical chain by (chain_id, block_number, log_index).

    The record is enriched with *generic, ABI-agnostic* transaction and receipt
    context (e.g., sender, recipient, value, gas usage, status, effective gas
    price and transaction type), so that downstream indexing and analytics
    can be performed without repeatedly joining raw.transactions and raw.receipts.

    All binary blockchain identifiers (addresses, hashes, topics) are stored
    as BYTEA to preserve canonical form and avoid formatting/normalisation
    concerns at this layer. Any decoding or ABI-level semantics are intentionally
    deferred to higher-level domain/indexing logic.

    This table is intended to be a stable, curated staging surface built from
    raw chain data, with strong typing, deterministic keys and indexes optimised
    for common lookup patterns (by contract, event signature and transaction).
    """

    __tablename__ = "evm_event_logs"
    __table_args__ = (
        # Natural primary key — uniquely identifies a log in the canonical chain
        PrimaryKeyConstraint("chain_id", "block_number", "log_index"),

        # Typical lookup pattern: contract + event + block range
        Index(
            "ix_logs_chain_address_topic0_block",
            "chain_id",
            "address",
            "topic0",
            "block_number",
        ),

        # Fast lookup by transaction
        Index(
            "ix_logs_chain_txhash",
            "chain_id",
            "transaction_hash",
        ),

        {"schema": "staging"},
    )

    # -------------------------------------------------------------------------
    # Block / chain context
    # -------------------------------------------------------------------------

    """Chain identifier (e.g., 1 = Ethereum mainnet)."""
    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)

    """Number of the block in which the log was emitted."""
    block_number: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # -------------------------------------------------------------------------
    # Transaction identity
    # -------------------------------------------------------------------------

    """Hash of the transaction that emitted the log (bytea)."""
    transaction_hash: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    """Index of the transaction within the block (0-based)."""
    transaction_index: Mapped[int] = mapped_column(Integer, nullable=False)

    """Index of the log within the block (0-based, deterministic ordering)."""
    log_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # -------------------------------------------------------------------------
    # Transaction context (generic, ABI-agnostic)
    # -------------------------------------------------------------------------

    """Sender address of the transaction (bytea)."""
    tx_from: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    """Recipient address of the transaction (bytea). Null for contract creations."""
    tx_to: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    """
    Transaction value in native token units (e.g., wei on Ethereum).
    Stored as NUMERIC to avoid precision loss.
    """
    tx_value: Mapped[Numeric] = mapped_column(Numeric, nullable=False)

    """
    Transaction type:
      0 = legacy,
      1 = access list,
      2 = EIP-1559,
    and so on (chain-specific). May be NULL on very old chains.
    """
    tx_type: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # -------------------------------------------------------------------------
    # Receipt context
    # -------------------------------------------------------------------------

    """
    Transaction status from receipt:
      1 = success,
      0 = failure,
      NULL = not available (e.g., pre-Byzantium or chain-specific behavior).
    """
    tx_status: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    """Gas used by this transaction (from receipt)."""
    tx_gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    """Cumulative gas used up to and including this transaction in the block."""
    tx_cumulative_gas_used: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    """Effective gas price paid for this transaction (from receipt, EIP-1559-aware)."""
    tx_effective_gas_price: Mapped[Numeric | None] = mapped_column(Numeric, nullable=True)

    # -------------------------------------------------------------------------
    # Log payload (EVM log fields)
    # -------------------------------------------------------------------------

    """Address of the contract that emitted the log (bytea)."""
    address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    """topic0 — keccak256 hash of the event signature (bytea)."""
    topic0: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    """topic1 — first indexed event argument (bytea)."""
    topic1: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    """topic2 — second indexed event argument (bytea)."""
    topic2: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    """topic3 — third indexed event argument (bytea)."""
    topic3: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)

    """Event data payload (ABI-encoded, non-indexed args; bytea)."""
    data: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
