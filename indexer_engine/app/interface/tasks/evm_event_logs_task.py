from __future__ import annotations

from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from indexer_engine.app.config import settings
from indexer_engine.app.domain.ports.out import EvmEventLogsIndexer
from indexer_engine.app.infrastructure.factories.evm_event_logs_indexer_factory import (
    evm_event_logs_indexer_factory,
)
from indexer_engine.app.application.services.index_evm_event_logs_for_block_range import (
    BlockRange,
    index_evm_event_logs_for_block_range,
)


_EARLIEST: Literal["earliest"] = "earliest"
_LATEST: Literal["latest"] = "latest"


def _create_async_engine() -> AsyncEngine:
    return create_async_engine(
        settings.database_url,  # postgresql+asyncpg://
        echo=False,
        pool_pre_ping=True,
    )


async def _resolve_block_bounds(
    *,
    engine: AsyncEngine,
    chain_id: int,
    from_block: int | str,
    to_block: int | str,
) -> tuple[int, int]:
    """
    Converts from_block / to_block into concrete block numbers.

    Responsibilities:
      - handle special values "earliest"/"latest" (or empty string),
      - ensure there is at least one row in raw.logs for given chain_id.
    """
    # Jeśli oba są intami, nie musimy pytać bazy o min/max.
    if isinstance(from_block, int) and isinstance(to_block, int):
        return from_block, to_block

    sql = text(
        """
        SELECT
            MIN(block_number) AS min_block,
            MAX(block_number) AS max_block
        FROM raw.logs
        WHERE chain_id = :chain_id
        """
    )

    async with engine.connect() as conn:
        result = await conn.execute(sql, {"chain_id": chain_id})
        row = result.one_or_none()

    if row is None or row.min_block is None or row.max_block is None:
        raise RuntimeError(f"No raw.logs found for chain_id={chain_id}")

    min_block: int = row.min_block
    max_block: int = row.max_block

    # from_block
    if isinstance(from_block, int):
        fb = from_block
    else:
        fb_str = from_block.strip().lower()
        if fb_str in ("", _EARLIEST):
            fb = min_block
        else:
            raise ValueError(f"Unsupported from_block value: {from_block!r}")

    # to_block
    if isinstance(to_block, int):
        tb = to_block
    else:
        tb_str = to_block.strip().lower()
        if tb_str in ("", _LATEST):
            tb = max_block
        else:
            raise ValueError(f"Unsupported to_block value: {to_block!r}")

    # Bez sprawdzania zakresu; to jest rola BlockRange.validate()
    return fb, tb


async def index_evm_event_logs_task(
    *,
    chain_id: int,
    from_block: int | str,
    to_block: int | str,
    backend: str = "sqlalchemy",
) -> None:
    """
    Indexes EVM logs into staging.evm_event_logs for a given chain and block range.

    from_block / to_block can be:
    - int (a specific block number),
    - "earliest" (the first available block in raw.logs),
    - "latest" (the last available block in raw.logs).
    """
    engine = _create_async_engine()
    try:
        resolved_from_block, resolved_to_block = await _resolve_block_bounds(
            engine=engine,
            chain_id=chain_id,
            from_block=from_block,
            to_block=to_block,
        )

        indexer: EvmEventLogsIndexer = evm_event_logs_indexer_factory(
            backend=backend,
            engine=engine,
        )

        await index_evm_event_logs_for_block_range(
            indexer=indexer,
            chain_id=chain_id,
            block_range=BlockRange(
                from_block=resolved_from_block,
                to_block=resolved_to_block,
            ),
        )
    finally:
        await engine.dispose()
