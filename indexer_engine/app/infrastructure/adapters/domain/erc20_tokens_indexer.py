from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from indexer_engine.app.domain.ports.out import Erc20TokenMetadataFetcher

import logging

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TokenRow:
    token_address: bytes


def _chunks(seq: list[Any], size: int) -> Iterable[list[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


class SqlAlchemyTokensIndexer:
    """
    Indexer adapter: fills domain.tokens by discovering token addresses from domain.uniswap_v4_pools
    and fetching on-chain ERC-20 metadata via eth_call.

    Strategy:
    - Select distinct token addresses from domain.uniswap_v4_pools (token0/token1).
    - Filter out zero-address (native sentinel).
    - Left join domain.tokens to index only missing/incomplete rows.
    - For each token, call Erc20TokenMetadataFetcher.
    - Upsert into domain.tokens (ON CONFLICT DO UPDATE) in batches.
    """

    _ZERO_ADDRESS_20B = b"\x00" * 20

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        fetcher: Erc20TokenMetadataFetcher,
        batch_size: int = 500,
    ) -> None:
        self._engine = engine
        self._fetcher = fetcher
        self._batch_size = batch_size

    async def index_tokens(
        self,
        *,
        chain_id: int,
        limit: int | None = None,
    ) -> None:
        logger.info(
            "Starting ERC20 tokens indexing",
            extra={"chain_id": chain_id, "limit": limit},
        )
        # 1) Discover candidate token addresses (distinct) from pools
        #    and select only those missing or incomplete in domain.tokens.
        #
        # "incomplete" = symbol IS NULL OR decimals IS NULL
        select_sql = text(
            """
            WITH candidates AS (
                SELECT DISTINCT token0_address AS token_address
                FROM domain.uniswap_v4_pools
                WHERE chain_id = :chain_id

                UNION

                SELECT DISTINCT token1_address AS token_address
                FROM domain.uniswap_v4_pools
                WHERE chain_id = :chain_id
            )
            SELECT
                c.token_address
            FROM candidates c
            LEFT JOIN domain.tokens t
              ON t.chain_id = :chain_id
             AND t.token_address = c.token_address
            WHERE c.token_address IS NOT NULL
              AND c.token_address <> :zero20
              AND (
                    t.token_address IS NULL
                 OR t.symbol IS NULL
                 OR t.decimals IS NULL
              )
            ORDER BY c.token_address
            """
            + ("" if limit is None else "\nLIMIT :limit")
        )

        upsert_sql = text(
            """
            INSERT INTO domain.tokens (
                chain_id,
                token_address,
                symbol,
                decimals,
                name,
                updated_at
            )
            VALUES (
                :chain_id,
                :token_address,
                :symbol,
                :decimals,
                :name,
                :updated_at
            )
            ON CONFLICT (chain_id, token_address) DO UPDATE SET
                symbol = COALESCE(EXCLUDED.symbol, domain.tokens.symbol),
                decimals = COALESCE(EXCLUDED.decimals, domain.tokens.decimals),
                name = COALESCE(EXCLUDED.name, domain.tokens.name),
                updated_at = EXCLUDED.updated_at
            """
        )

        params: dict[str, Any] = {
            "chain_id": chain_id,
            "zero20": self._ZERO_ADDRESS_20B,
        }
        if limit is not None:
            params["limit"] = limit

        async with self._engine.begin() as conn:
            result = await conn.execute(select_sql, params)

            all_rows = result.mappings().all()
            total = len(all_rows)

            logger.info(
                "Discovered %s token candidates for metadata fetch",
                total,
            )

            batch_addrs: list[_TokenRow] = []
            payload: list[dict[str, Any]] = []

            def _flush_payload_now() -> datetime:
                # Keep a single timestamp per flush (nicer for debugging)
                return datetime.now(timezone.utc)

            for batch_idx, rows in enumerate(
                _chunks(all_rows, self._batch_size), start=1
            ):
                processed = min(batch_idx * self._batch_size, total)

                logger.info(
                    "Processing token batch %s (%s/%s)",
                    batch_idx,
                    processed,
                    total,
                )

                batch_addrs: list[_TokenRow] = []

                for r in rows:
                    token_address = r["token_address"]
                    # asyncpg might return memoryview; normalize to bytes
                    if isinstance(token_address, memoryview):
                        token_address = token_address.tobytes()
                    batch_addrs.append(
                        _TokenRow(token_address=bytes(token_address))
                    )

                # 2) Fetch metadata (sequential by default; safe and simple)
                ts = _flush_payload_now()
                payload.clear()

                fetch_errors = 0

                for tr in batch_addrs:
                    try:
                        meta = await self._fetcher.fetch(
                            chain_id=chain_id,
                            token_address=tr.token_address,
                        )
                    except Exception:
                        fetch_errors += 1
                        meta = {}

                    payload.append(
                        {
                            "chain_id": chain_id,
                            "token_address": tr.token_address,
                            "symbol": meta.get("symbol"),
                            "decimals": meta.get("decimals"),
                            "name": meta.get("name"),
                            "updated_at": ts,
                        }
                    )

                if payload:
                    await conn.execute(upsert_sql, payload)

                    logger.info(
                        "Upserted %s tokens into domain.tokens (fetch_errors=%s)",
                        len(payload),
                        fetch_errors,
                    )

                    payload.clear()

            logger.info(
                "Finished ERC20 tokens indexing",
                extra={"chain_id": chain_id, "total": total},
            )