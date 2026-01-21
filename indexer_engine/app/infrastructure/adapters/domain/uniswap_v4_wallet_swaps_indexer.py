from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import EvmEventDecoder


class SqlAlchemyUniswapV4WalletSwapsIndexer:
    """
    Indexer adapter: projects Swap events from analytics.evm_events into
    domain.uniswap_v4_wallet_swaps.

    Strategy:
    - SQL filters only candidate rows by (chain_id, block range, topic0).
    - Python decodes event payload (topics1-3 + data) using EvmEventDecoder.
    - Inserts decoded swaps into domain table in batches with ON CONFLICT DO NOTHING.
    """

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        decoder: EvmEventDecoder,
        topic0_as_sql_filter: bytes,
        batch_size: int = 10_000,
    ) -> None:
        self._engine = engine
        self._decoder = decoder
        self._topic0_filter = topic0_as_sql_filter
        self._batch_size = batch_size

    async def index_swaps_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        select_sql = text(
            """
            SELECT
                e.chain_id,
                e.block_number,
                b.timestamp AS block_timestamp,
                e.transaction_hash,
                e.transaction_index,
                e.log_index,
                e.tx_from_address,
                e.contract_address,
                e.event_signature,
                e.topic0,
                e.topic1,
                e.topic2,
                e.topic3,
                e.data
            FROM analytics.evm_events e
            JOIN analytics.blocks b
              ON b.chain_id = e.chain_id
             AND b.block_number = e.block_number
            WHERE e.chain_id = :chain_id
              AND e.block_number BETWEEN :from_block AND :to_block
              AND e.topic0 = :topic0
            ORDER BY e.block_number, e.transaction_index, e.log_index
            """
        )

        insert_sql = text(
            """
            INSERT INTO domain.uniswap_v4_wallet_swaps (
                chain_id,
                block_number,
                block_timestamp,
                transaction_hash,
                transaction_index,
                log_index,
                wallet_address,
                pool_manager,
                pool_id,
                sender,
                amount0,
                amount1,
                sqrt_price_x96,
                liquidity,
                tick,
                event_signature
            )
            VALUES (
                :chain_id,
                :block_number,
                :block_timestamp,
                :transaction_hash,
                :transaction_index,
                :log_index,
                :wallet_address,
                :pool_manager,
                :pool_id,
                :sender,
                :amount0,
                :amount1,
                :sqrt_price_x96,
                :liquidity,
                :tick,
                :event_signature
            )
            ON CONFLICT (chain_id, transaction_hash, log_index) DO NOTHING
            """
        )

        async with self._engine.begin() as conn:
            result = await conn.execute(
                select_sql,
                {
                    "chain_id": chain_id,
                    "from_block": from_block,
                    "to_block": to_block,
                    "topic0": self._topic0_filter,
                },
            )

            payload: list[dict[str, Any]] = []

            while True:
                batch = result.mappings().fetchmany(self._batch_size)
                if not batch:
                    break

                for r in batch:
                    decoded = self._decoder.decode(
                        topic0=r["topic0"],
                        topic1=r["topic1"],
                        topic2=r["topic2"],
                        topic3=r["topic3"],
                        data=r["data"],
                    )
                    if not decoded:
                        continue

                    payload.append(
                        {
                            "chain_id": r["chain_id"],
                            "block_number": r["block_number"],
                            "block_timestamp": r["block_timestamp"],
                            "transaction_hash": r["transaction_hash"],
                            "transaction_index": r["transaction_index"],
                            "log_index": r["log_index"],
                            "wallet_address": r["tx_from_address"],  # MVP attribution
                            "pool_manager": r["contract_address"],
                            "pool_id": decoded["pool_id"],
                            "sender": decoded.get("sender"),
                            "amount0": decoded["amount0"],
                            "amount1": decoded["amount1"],
                            "sqrt_price_x96": decoded.get("sqrt_price_x96"),
                            "liquidity": decoded.get("liquidity"),
                            "tick": decoded.get("tick"),
                            "event_signature": r["event_signature"],
                        }
                    )

                if payload:
                    await conn.execute(insert_sql, payload)
                    payload.clear()