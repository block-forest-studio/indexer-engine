import asyncio
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from web3 import Web3

from indexer_engine.app.infrastructure.db.engine import create_app_async_engine
from indexer_engine.app.infrastructure.db.models.analytics.event_signatures import (
    AnalyticsEventSignaturesDB,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ABI_PATH = PROJECT_ROOT / "indexer_engine" / "app" / "registry" / "abi" / "PoolManager.json"  # albo zostaw ./PoolManager.json, jeśli tak trzymasz


def event_signature(evt: dict) -> str:
    name = evt["name"]
    types = [inp["type"] for inp in evt["inputs"]]
    return f"{name}({','.join(types)})"


async def seed_event_signatures() -> None:
    with ABI_PATH.open() as f:
        abi = json.load(f)

    events = [item for item in abi if item.get("type") == "event"]
    # for e in events:
    #     print(e)
    #     print(" ")

    values: list[dict] = []
    for evt in events:
        sig = event_signature(evt)  # "Swap(address,...)"
        topic0 = Web3.keccak(text=sig)  # bytes(32)

        values.append(
            {
                "topic0": bytes(topic0),
                "event_name": evt["name"],
                "event_signature": sig,
            }
        )

    engine = create_app_async_engine()
    stmt = insert(AnalyticsEventSignaturesDB).values(values)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=[AnalyticsEventSignaturesDB.topic0]
    )

    async with engine.begin() as conn:
        await conn.execute(stmt)


if __name__ == "__main__":
    asyncio.run(seed_event_signatures())
