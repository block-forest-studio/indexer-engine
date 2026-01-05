from __future__ import annotations

from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


BlockSelector = int | str
_EARLIEST: Literal["earliest"] = "earliest"
_LATEST: Literal["latest"] = "latest"


async def resolve_block_bounds_from_table(
    *,
    engine: AsyncEngine,
    chain_id: int,
    from_block: BlockSelector,
    to_block: BlockSelector,
    source_table: str,
) -> tuple[int, int]:
    """
    Resolve from_block / to_block into concrete block numbers using a given source table.

    - If both are ints -> they are returned as-is.
    - If from_block is "earliest" / "" -> MIN(block_number) from source_table.
    - If to_block is "latest" / ""     -> MAX(block_number) from source_table.

    Assumes source_table has columns:
      - chain_id
      - block_number
    """
    if isinstance(from_block, int) and isinstance(to_block, int):
        return from_block, to_block

    sql = text(
        f"""
        SELECT
            MIN(block_number) AS min_block,
            MAX(block_number) AS max_block
        FROM {source_table}
        WHERE chain_id = :chain_id
        """
    )

    async with engine.connect() as conn:
        result = await conn.execute(sql, {"chain_id": chain_id})
        row = result.one_or_none()

    if row is None or row.min_block is None or row.max_block is None:
        raise RuntimeError(f"No rows found in {source_table!r} for chain_id={chain_id}")

    min_block: int = row.min_block
    max_block: int = row.max_block

    if isinstance(from_block, int):
        fb = from_block
    else:
        fb_str = from_block.strip().lower()
        if fb_str in ("", _EARLIEST):
            fb = min_block
        else:
            raise ValueError(f"Unsupported from_block value: {from_block!r}")

    if isinstance(to_block, int):
        tb = to_block
    else:
        tb_str = to_block.strip().lower()
        if tb_str in ("", _LATEST):
            tb = max_block
        else:
            raise ValueError(f"Unsupported to_block value: {to_block!r}")

    return fb, tb
