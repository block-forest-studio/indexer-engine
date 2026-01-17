from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


# TODO: in the next step, replace this with the proper decoder from the ABI
class UniswapV4SwapDecoder:
    def decode(
        self,
        *,
        topic0: bytes | None,
        topic1: bytes | None,
        topic2: bytes | None,
        topic3: bytes | None,
        data: bytes,
    ) -> dict[str, Any] | None:
        """
        Return decoded fields for Uniswap v4 Swap, or None if not decodable / not a swap.
        """
        raise NotImplementedError


class SqlAlchemyUniswapV4WalletSwapsIndexer:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        decoder: UniswapV4SwapDecoder,
        swap_topic0: bytes,
        batch_size: int = 10_000,
    ) -> None:
        self._engine = engine
        self._decoder = decoder
        self._swap_topic0 = swap_topic0
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
            WHERE e.chain_id = :chain_id
              AND e.block_number BETWEEN :from_block AND :to_block
              AND e.topic0 IS NOT NULL
              AND e.topic0 = :swap_topic0
            ORDER BY e.block_number, e.transaction_index, e.log_index
            """
        )

        insert_sql = text(
            """
            INSERT INTO domain.uniswap_v4_wallet_swaps (
                chain_id,
                block_number,
                transaction_hash,
                transaction_index,
                log_index,
                wallet_address,
                pool_manager,
                pool_id,
                sender,
                recipient,
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
                :transaction_hash,
                :transaction_index,
                :log_index,
                :wallet_address,
                :pool_manager,
                :pool_id,
                :sender,
                :recipient,
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
            res = await conn.execute(
                select_sql,
                {
                    "chain_id": chain_id,
                    "from_block": from_block,
                    "to_block": to_block,
                    "swap_topic0": self._swap_topic0,
                },
            )
            rows = res.mappings().all()

            payload: list[dict[str, Any]] = []
            for r in rows:
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
                        "transaction_hash": r["transaction_hash"],
                        "transaction_index": r["transaction_index"],
                        "log_index": r["log_index"],
                        "wallet_address": r["tx_from_address"],  # MVP attribution
                        "pool_manager": r["contract_address"],
                        "pool_id": decoded["pool_id"],
                        "sender": decoded.get("sender"),
                        "recipient": decoded.get("recipient"),
                        "amount0": decoded["amount0"],
                        "amount1": decoded["amount1"],
                        "sqrt_price_x96": decoded.get("sqrt_price_x96"),
                        "liquidity": decoded.get("liquidity"),
                        "tick": decoded.get("tick"),
                        "event_signature": r["event_signature"],
                    }
                )

                if len(payload) >= self._batch_size:
                    await conn.execute(insert_sql, payload)
                    payload.clear()

            if payload:
                await conn.execute(insert_sql, payload)
