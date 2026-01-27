
from __future__ import annotations

from datetime import datetime
from indexer_engine.app.infrastructure.db.db_base import BaseDB

from sqlalchemy import (
    Integer,
    Index,
    PrimaryKeyConstraint,
    DateTime,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import BYTEA


class TokensDB(BaseDB):
    """
    Token metadata registry (ERC-20).

    One row = one token address per chain_id with resolved symbol/decimals.
    This is shared enrichment data used by API projections.
    """

    __tablename__ = "tokens"
    __table_args__ = (
        PrimaryKeyConstraint("chain_id", "token_address"),
        Index("ix_tokens_chain_symbol", "chain_id", "symbol"),
        {"schema": "domain"},
    )

    chain_id: Mapped[int] = mapped_column(Integer, nullable=False)
    token_address: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    decimals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )