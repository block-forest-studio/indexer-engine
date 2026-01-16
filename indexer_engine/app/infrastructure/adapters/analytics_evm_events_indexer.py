from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class SqlAlchemyAnalyticsEvmEventsIndexer:
    """
    AnalyticsEvmEventsIndexer implementation using SQLAlchemy + raw SQL.

    Responsibilities:
    - project rows from staging.evm_event_logs into analytics.evm_events,
    - perform the operation in a set-based, idempotent way,
    - provide a minimal enrichment for analytics:
      - contract_address (from log.address),
      - tx_* context (from staging),
      - event_name / event_signature placeholders.

    Notes:
    - event_name is currently a static placeholder ('unknown') for MVP,
      to be replaced by ABI-based resolution in a subsequent iteration.
    - event_signature is derived from topic0 as '0x' || encode(topic0, 'hex'),
      or 'unknown' if topic0 is NULL.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def index_events_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        """
        Index a given block range into analytics.evm_events.

        Source:
          - staging.evm_event_logs

        Target:
          - analytics.evm_events

        Idempotency:
          - enforced by ON CONFLICT (chain_id, transaction_hash, log_index) DO NOTHING.
        """
        sql = text(
            """
            INSERT INTO analytics.evm_events (
                chain_id,
                block_number,
                transaction_hash,
                transaction_index,
                log_index,
                tx_gas_used,
                tx_effective_gas_price,
                tx_value,
                tx_from_address,
                tx_to_address,
                contract_address,
                topic0,
                topic1,
                topic2,
                topic3,
                data,
                event_name,
                event_signature
            )
            SELECT
                l.chain_id,
                l.block_number,
                l.transaction_hash,
                l.transaction_index,
                l.log_index,
                l.tx_gas_used,
                l.tx_effective_gas_price,
                l.tx_value,
                l.tx_from,
                l.tx_to,
                l.address,
                l.topic0,
                l.topic1,
                l.topic2,
                l.topic3,
                l.data,
                COALESCE(es.event_name, 'unknown') AS event_name,
                COALESCE(
                    es.event_signature,
                    CASE
                        WHEN l.topic0 IS NULL THEN 'unknown'
                        ELSE '0x' || encode(l.topic0, 'hex')
                    END
                ) AS event_signature
            FROM staging.evm_event_logs AS l
            LEFT JOIN analytics.event_signatures es
              ON es.topic0 = l.topic0
            WHERE l.chain_id = :chain_id
              AND l.block_number BETWEEN :from_block AND :to_block
            ON CONFLICT (chain_id, transaction_hash, log_index) DO NOTHING;
            """
        )

        async with self._engine.begin() as conn:
            await conn.execute(
                sql,
                {
                    "chain_id": chain_id,
                    "from_block": from_block,
                    "to_block": to_block,
                },
            )
