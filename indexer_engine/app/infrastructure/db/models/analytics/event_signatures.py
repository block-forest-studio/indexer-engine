from __future__ import annotations

from sqlalchemy import PrimaryKeyConstraint, Text
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from indexer_engine.app.infrastructure.db.db_base import BaseDB


class AnalyticsEventSignaturesDB(BaseDB):
    """
    Dictionary of known EVM event signatures.

    One row maps a topic0 (keccak of "EventName(type1,type2,...)") to:
    - event_name        e.g. "Swap"
    - event_signature   e.g. "Swap(address,address,int256,int256,uint160,uint128,int24)"
    """

    __tablename__ = "event_signatures"
    __table_args__ = (
        PrimaryKeyConstraint("topic0"),
        {"schema": "analytics"},
    )

    # topic0 = keccak("EventName(type1,type2,...)") as raw bytes32
    topic0: Mapped[bytes] = mapped_column(BYTEA, nullable=False)

    # Short name, e.g. "Swap"
    event_name: Mapped[str] = mapped_column(Text, nullable=False)

    # Full canonical signature, e.g. "Swap(address,address,int256,int256,uint160,uint128,int24)"
    event_signature: Mapped[str] = mapped_column(Text, nullable=False)
