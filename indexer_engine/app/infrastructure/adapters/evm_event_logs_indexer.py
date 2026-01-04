from __future__ import annotations

import logging
from typing import Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)

_DEFAULT_BLOCK_BATCH_SIZE: Final[int] = 10_000


_INSERT_EVM_EVENT_LOGS_SQL = text(
    """
    INSERT INTO staging.evm_event_logs (
        chain_id,
        block_number,
        transaction_hash,
        transaction_index,
        log_index,
        tx_from,
        tx_to,
        tx_value,
        tx_type,
        tx_status,
        tx_gas_used,
        tx_cumulative_gas_used,
        tx_effective_gas_price,
        address,
        topic0,
        topic1,
        topic2,
        topic3,
        data
    )
    SELECT
        l.chain_id                              AS chain_id,
        l.block_number                          AS block_number,
        l.transaction_hash                      AS transaction_hash,
        t.transaction_index                     AS transaction_index,
        l.log_index                             AS log_index,
        t."from"                                AS tx_from,
        t."to"                                  AS tx_to,
        t.value                                 AS tx_value,
        t."type"                                AS tx_type,
        r.status                                AS tx_status,
        r.gas_used                              AS tx_gas_used,
        r.cumulative_gas_used                   AS tx_cumulative_gas_used,
        r.effective_gas_price                   AS tx_effective_gas_price,
        l.address                               AS address,
        l.topic0                                AS topic0,
        l.topic1                                AS topic1,
        l.topic2                                AS topic2,
        l.topic3                                AS topic3,
        l.data                                  AS data
    FROM raw.logs AS l
    JOIN raw.transactions AS t
      ON t.chain_id = l.chain_id
     AND t.hash     = l.transaction_hash
    JOIN raw.receipts AS r
      ON r.chain_id         = l.chain_id
     AND r.transaction_hash = l.transaction_hash
    WHERE l.chain_id = :chain_id
      AND l.block_number BETWEEN :from_block AND :to_block
    ON CONFLICT (chain_id, block_number, log_index) DO NOTHING;
    """
)


class SqlAlchemyEvmEventLogsIndexer:
    """
    PostgreSQL/SQLAlchemy implementation of EvmEventLogsIndexer.

    Uses a set-based INSERT ... SELECT ... ON CONFLICT DO NOTHING
    to populate staging.evm_event_logs from raw.* tables in batches.
    """

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        block_batch_size: int = _DEFAULT_BLOCK_BATCH_SIZE,
    ) -> None:
        if block_batch_size <= 0:
            raise ValueError("block_batch_size must be positive")
        self._engine = engine
        self._block_batch_size = block_batch_size

    async def index_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        if from_block < 0 or to_block < 0:
            raise ValueError("Block numbers must be non-negative")
        if from_block > to_block:
            raise ValueError("from_block must be <= to_block")

        logger.info(
            "Indexing EVM event logs: chain_id=%s, blocks=[%s, %s], batch_size=%s",
            chain_id,
            from_block,
            to_block,
            self._block_batch_size,
        )

        async with self._engine.begin() as conn:
            current = from_block
            while current <= to_block:
                batch_from = current
                batch_to = min(current + self._block_batch_size - 1, to_block)

                logger.debug(
                    "Indexing batch: chain_id=%s, blocks=[%s, %s]",
                    chain_id,
                    batch_from,
                    batch_to,
                )

                result = await conn.execute(
                    _INSERT_EVM_EVENT_LOGS_SQL,
                    {
                        "chain_id": chain_id,
                        "from_block": batch_from,
                        "to_block": batch_to,
                    },
                )

                logger.debug(
                    "Batch indexed: chain_id=%s, blocks=[%s, %s], inserted_rowcount=%s",
                    chain_id,
                    batch_from,
                    batch_to,
                    getattr(result, "rowcount", None),
                )

                current = batch_to + 1

        logger.info(
            "Finished indexing EVM event logs: chain_id=%s, blocks=[%s, %s]",
            chain_id,
            from_block,
            to_block,
        )
