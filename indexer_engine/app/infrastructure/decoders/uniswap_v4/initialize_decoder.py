from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from eth_abi import decode as abi_decode
from eth_utils import keccak

from indexer_engine.app.domain.ports.out import EvmEventDecoder


class InitializeDecoder(EvmEventDecoder):
    """
    ABI-based decoder for Uniswap v4 PoolManager.Initialize event.

    PoolManager ABI (from your paste):
      event Initialize(
          bytes32 indexed id,
          address indexed currency0,
          address indexed currency1,
          uint24 fee,
          int24 tickSpacing,
          address hooks,
          uint160 sqrtPriceX96,
          int24 tick
      )

    Topics:
      topic0 = keccak("Initialize(bytes32,address,address,uint24,int24,address,uint160,int24)")
      topic1 = id (bytes32)
      topic2 = currency0 (address, as 32-byte topic)
      topic3 = currency1 (address, as 32-byte topic)

    Data (non-indexed):
      fee, tickSpacing, hooks, sqrtPriceX96, tick
    """

    def __init__(self, *, abi_path: Path, event_name: str = "Initialize") -> None:
        self._abi = self._load_abi(abi_path)
        self._event_abi = self._find_event(self._abi, event_name)
        self._signature = self._event_signature(self._event_abi)
        self._topic0 = keccak(text=self._signature)

        self._inputs: list[dict[str, Any]] = list(self._event_abi.get("inputs", []))
        self._indexed_inputs = [i for i in self._inputs if i.get("indexed") is True]
        self._non_indexed_inputs = [i for i in self._inputs if not i.get("indexed")]

        self._non_indexed_types = [i["type"] for i in self._non_indexed_inputs]
        self._non_indexed_names = [i["name"] for i in self._non_indexed_inputs]

        # Defensive sanity: in your ABI Initialize has 3 indexed inputs
        if len(self._indexed_inputs) != 3:
            # Not fatal, but indicates ABI differs from what this decoder expects.
            # Keep it as a guardrail.
            indexed_names = [i.get("name") for i in self._indexed_inputs]
            raise ValueError(
                f"Unexpected Initialize indexed inputs count={len(self._indexed_inputs)} names={indexed_names}. "
                "Expected 3 indexed inputs: id, currency0, currency1."
            )

    @property
    def topic0(self) -> bytes:
        return self._topic0

    @property
    def event_signature(self) -> str:
        return self._signature

    def decode(
        self,
        *,
        topic0: bytes | None,
        topic1: bytes | None,
        topic2: bytes | None,
        topic3: bytes | None,
        data: bytes,
    ) -> dict[str, Any] | None:
        # 1) must match expected event
        if topic0 is None or topic0 != self._topic0:
            return None

        # 2) Initialize has 3 indexed topics: id, currency0, currency1
        if topic1 is None or topic2 is None or topic3 is None:
            return None

        pool_id = self._as_bytes32(topic1)
        currency0 = self._topic_as_address(topic2)
        currency1 = self._topic_as_address(topic3)

        # 3) Decode non-indexed from data (fee, tickSpacing, hooks, sqrtPriceX96, tick)
        decoded_non_indexed = self._decode_non_indexed_data(data)

        out: dict[str, Any] = {
            "pool_id": pool_id,
            "currency0": currency0,
            "currency1": currency1,
            "fee": decoded_non_indexed.get("fee"),
            "tick_spacing": decoded_non_indexed.get("tickSpacing")
            if "tickSpacing" in decoded_non_indexed
            else decoded_non_indexed.get("tick_spacing"),
            "hooks": decoded_non_indexed.get("hooks"),
            # not needed for domain.uniswap_v4_pools right now, but decoded for completeness/debug:
            "sqrt_price_x96": decoded_non_indexed.get("sqrtPriceX96")
            if "sqrtPriceX96" in decoded_non_indexed
            else decoded_non_indexed.get("sqrt_price_x96"),
            "tick": decoded_non_indexed.get("tick"),
        }

        # Minimal sanity: pool_id + currencies are mandatory for pools registry
        if out["pool_id"] is None or out["currency0"] is None or out["currency1"] is None:
            return None

        return out

    # ---------------------------------------------------------------------
    # ABI helpers (copied style from your SwapDecoder)
    # ---------------------------------------------------------------------

    def _load_abi(self, abi_path: Path) -> list[dict[str, Any]]:
        if not abi_path.exists():
            raise FileNotFoundError(f"ABI file not found: {abi_path}")
        raw = abi_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        if isinstance(data, list):
            abi = data
        elif isinstance(data, dict) and "abi" in data and isinstance(data["abi"], list):
            abi = data["abi"]
        else:
            raise ValueError(
                f"Unsupported ABI JSON format in {abi_path}. Expected list or dict with 'abi' list."
            )

        return [x for x in abi if isinstance(x, dict)]

    def _find_event(self, abi: list[dict[str, Any]], event_name: str) -> dict[str, Any]:
        events = [x for x in abi if x.get("type") == "event" and x.get("name") == event_name]
        if not events:
            names = sorted({x.get("name") for x in abi if x.get("type") == "event"})
            raise ValueError(f"Event {event_name!r} not found in ABI. Available events: {names}")
        if len(events) > 1:
            raise ValueError(
                f"Multiple events named {event_name!r} found in ABI. Disambiguation by full signature is required."
            )
        return events[0]

    def _event_signature(self, event_abi: Mapping[str, Any]) -> str:
        name = event_abi.get("name")
        inputs = event_abi.get("inputs", [])
        if not isinstance(name, str) or not isinstance(inputs, list):
            raise ValueError("Invalid event ABI: missing name/inputs")
        types: list[str] = []
        for inp in inputs:
            if not isinstance(inp, dict) or "type" not in inp:
                raise ValueError("Invalid event ABI inputs")
            types.append(inp["type"])
        return f"{name}({','.join(types)})"

    def _decode_non_indexed_data(self, data: bytes) -> dict[str, Any]:
        if not self._non_indexed_inputs:
            return {}
        values = abi_decode(self._non_indexed_types, data)

        out: dict[str, Any] = {}
        for name, typ, val in zip(
            self._non_indexed_names, self._non_indexed_types, values, strict=True
        ):
            out[name] = self._normalize_abi_value(typ, val)
        return out

    # ---------------------------------------------------------------------
    # Topic / ABI value normalization
    # ---------------------------------------------------------------------

    def _as_bytes32(self, b: bytes) -> bytes:
        if len(b) != 32:
            bb = bytes(b)
            if len(bb) == 32:
                return bb
            raise ValueError(f"Expected 32 bytes (bytes32 topic), got len={len(bb)}")
        return b

    def _topic_as_address(self, topic: bytes) -> bytes:
        t = self._as_bytes32(topic)
        return t[-20:]

    def _normalize_abi_value(self, typ: str, val: Any) -> Any:
        if typ == "address":
            if isinstance(val, (bytes, bytearray)) and len(val) == 20:
                return bytes(val)
            if isinstance(val, int):
                return val.to_bytes(20, byteorder="big", signed=False)
            if isinstance(val, str):
                # eth_abi often returns "0x..." for address
                s = val.lower()
                if s.startswith("0x"):
                    s = s[2:]
                # left-pad if needed
                s = s.rjust(40, "0")
                return bytes.fromhex(s)
            return val

        if typ.startswith("uint") or typ.startswith("int"):
            if isinstance(val, int):
                return val
            return int(val)

        if typ.startswith("bytes"):
            if isinstance(val, (bytes, bytearray, memoryview)):
                return bytes(val)
            return val

        return val
