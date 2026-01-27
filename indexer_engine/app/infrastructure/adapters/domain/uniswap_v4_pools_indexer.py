from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import EvmEventDecoder


class SqlAlchemyUniswapV4PoolsIndexer:
    """
    Indexer adapter: projects PoolManager Initialize events from analytics.evm_events
    into domain.uniswap_v4_pools.

    Strategy:
    - SQL filters only candidate rows by (chain_id, block range, topic0).
    - Python decodes Initialize payload using EvmEventDecoder.
    - Inserts pools into domain table in batches with ON CONFLICT DO NOTHING.

    Notes:
    - This table acts as a registry: pool_id -> token0/token1 addresses (+ optional config fields).
    - created_block/created_timestamp are derived from the block of the Initialize event.
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

    async def index_pools_for_block_range(
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
                e.contract_address,
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
            INSERT INTO domain.uniswap_v4_pools (
                chain_id,
                pool_id,
                pool_manager,
                token0_address,
                token1_address,
                fee,
                tick_spacing,
                hooks,
                created_block,
                created_timestamp
            )
            VALUES (
                :chain_id,
                :pool_id,
                :pool_manager,
                :token0_address,
                :token1_address,
                :fee,
                :tick_spacing,
                :hooks,
                :created_block,
                :created_timestamp
            )
            ON CONFLICT (chain_id, pool_id) DO NOTHING
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

                    # Expected decoded keys for Initialize:
                    # - pool_id (bytes32)
                    # - currency0 (address/bytes20)
                    # - currency1 (address/bytes20)
                    # - fee (uint24/int) [optional]
                    # - tick_spacing (int24/int) [optional]
                    # - hooks (address) [optional]
                    pool_id = decoded["pool_id"]
                    token0 = decoded.get("currency0") or decoded.get("token0") or decoded.get("token0_address")
                    token1 = decoded.get("currency1") or decoded.get("token1") or decoded.get("token1_address")

                    # If your decoder uses different names, adjust above mapping.
                    if token0 is None or token1 is None:
                        # Can't build pool registry row without token addresses.
                        continue

                    payload.append(
                        {
                            "chain_id": r["chain_id"],
                            "pool_id": pool_id,
                            "pool_manager": r["contract_address"],
                            "token0_address": token0,
                            "token1_address": token1,
                            "fee": decoded.get("fee"),
                            "tick_spacing": decoded.get("tick_spacing"),
                            "hooks": decoded.get("hooks"),
                            "created_block": r["block_number"],
                            "created_timestamp": r["block_timestamp"],
                        }
                    )

                if payload:
                    await conn.execute(insert_sql, payload)
                    payload.clear()
