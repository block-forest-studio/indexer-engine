from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from eth_abi import decode as abi_decode
from eth_utils import keccak

from indexer_engine.app.domain.ports.out import EvmEventDecoder


class SwapDecoder(EvmEventDecoder):
    """
    ABI-based decoder for a single Uniswap v4 PoolManager event (e.g. Swap).

    It:
    - loads ABI from a JSON file,
    - finds the event ABI by name,
    - computes topic0 = keccak("EventName(type1,type2,...)"),
    - decodes indexed args from topics (address/bytes32),
    - decodes non-indexed args from `data` with eth_abi.

    Output dict is tailored for Swap -> domain.uniswap_v4_wallet_swaps.
    """

    def __init__(self, *, abi_path: Path, event_name: str) -> None:
        self._abi = self._load_abi(abi_path)
        self._event_abi = self._find_event(self._abi, event_name)
        self._signature = self._event_signature(self._event_abi)
        self._topic0 = keccak(text=self._signature)

        # Cache inputs split
        self._inputs: list[dict[str, Any]] = list(self._event_abi.get("inputs", []))
        self._indexed_inputs = [i for i in self._inputs if i.get("indexed") is True]
        self._non_indexed_inputs = [i for i in self._inputs if not i.get("indexed")]

        self._non_indexed_types = [i["type"] for i in self._non_indexed_inputs]
        self._non_indexed_names = [i["name"] for i in self._non_indexed_inputs]

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

        # 2) For PoolManager.Swap expected indexed:
        #    topic1: id (bytes32)
        #    topic2: sender (address)
        #    topic3: none
        if topic1 is None or topic2 is None:
            return None

        pool_id = self._as_bytes32(topic1)
        sender = self._topic_as_address(topic2)

        # 3) Decode non-indexed from data using ABI (generic)
        decoded_non_indexed = self._decode_non_indexed_data(data)

        # 4) Map into the contract we need for domain.uniswap_v4_wallet_swaps
        # Swap non-indexed from ABI you pasted:
        # amount0 (int128), amount1 (int128), sqrtPriceX96 (uint160),
        # liquidity (uint128), tick (int24), fee (uint24)
        #
        # We don't store fee currently; ignore it.
        out: dict[str, Any] = {
            "pool_id": pool_id,
            "sender": sender,
            "recipient": None,  # Swap event doesn't include recipient in this ABI
            "amount0": decoded_non_indexed.get("amount0"),
            "amount1": decoded_non_indexed.get("amount1"),
            "sqrt_price_x96": decoded_non_indexed.get("sqrtPriceX96")
            if "sqrtPriceX96" in decoded_non_indexed
            else decoded_non_indexed.get("sqrt_price_x96"),
            "liquidity": decoded_non_indexed.get("liquidity"),
            "tick": decoded_non_indexed.get("tick"),
        }

        # Minimal sanity: required fields
        if out["amount0"] is None or out["amount1"] is None or out["pool_id"] is None:
            return None

        return out

    # ---------------------------------------------------------------------
    # ABI helpers
    # ---------------------------------------------------------------------

    def _load_abi(self, abi_path: Path) -> list[dict[str, Any]]:
        if not abi_path.exists():
            raise FileNotFoundError(f"ABI file not found: {abi_path}")
        raw = abi_path.read_text(encoding="utf-8")
        data = json.loads(raw)

        # Common formats:
        # - [ ... ] (ABI list)
        # - { "abi": [ ... ] } (artifact)
        if isinstance(data, list):
            abi = data
        elif isinstance(data, dict) and "abi" in data and isinstance(data["abi"], list):
            abi = data["abi"]
        else:
            raise ValueError(
                f"Unsupported ABI JSON format in {abi_path}. Expected list or dict with 'abi' list."
            )

        # Ensure dicts
        return [x for x in abi if isinstance(x, dict)]

    def _find_event(self, abi: list[dict[str, Any]], event_name: str) -> dict[str, Any]:
        events = [x for x in abi if x.get("type") == "event" and x.get("name") == event_name]
        if not events:
            names = sorted({x.get("name") for x in abi if x.get("type") == "event"})
            raise ValueError(
                f"Event {event_name!r} not found in ABI. Available events: {names}"
            )
        if len(events) > 1:
            # Overloaded event names are rare but possible; you may need a signature-based selector then.
            # For now, be explicit.
            raise ValueError(
                f"Multiple events named {event_name!r} found in ABI. "
                "Disambiguation by full signature is required."
            )
        return events[0]

    def _event_signature(self, event_abi: Mapping[str, Any]) -> str:
        name = event_abi.get("name")
        inputs = event_abi.get("inputs", [])
        if not isinstance(name, str) or not isinstance(inputs, list):
            raise ValueError("Invalid event ABI: missing name/inputs")
        types = []
        for inp in inputs:
            if not isinstance(inp, dict) or "type" not in inp:
                raise ValueError("Invalid event ABI inputs")
            types.append(inp["type"])
        return f"{name}({','.join(types)})"

    def _decode_non_indexed_data(self, data: bytes) -> dict[str, Any]:
        # If event has no non-indexed inputs, data should be empty
        if not self._non_indexed_inputs:
            return {}

        # Defensive: eth_abi expects bytes-like; empty is acceptable if no inputs
        values = abi_decode(self._non_indexed_types, data)

        out: dict[str, Any] = {}
        for name, typ, val in zip(self._non_indexed_names, self._non_indexed_types, values, strict=True):
            out[name] = self._normalize_abi_value(typ, val)
        return out

    # ---------------------------------------------------------------------
    # Topic / ABI value normalization
    # ---------------------------------------------------------------------

    def _as_bytes32(self, b: bytes) -> bytes:
        # Topic is always 32 bytes; keep it as is.
        if len(b) != 32:
            # Sometimes drivers return memoryview or shorter; normalize
            bb = bytes(b)
            if len(bb) == 32:
                return bb
            raise ValueError(f"Expected 32 bytes (bytes32 topic), got len={len(bb)}")
        return b

    def _topic_as_address(self, topic: bytes) -> bytes:
        # Indexed address is stored as 32-byte topic, right-padded (left-zero padded).
        t = self._as_bytes32(topic)
        return t[-20:]

    def _normalize_abi_value(self, typ: str, val: Any) -> Any:
        # eth_abi returns Python ints for int/uint* (including int128/int24).
        # bytes32 -> bytes, address in non-indexed would be 20 bytes, but here we only have uint/int/...
        if typ == "address":
            if isinstance(val, (bytes, bytearray)) and len(val) == 20:
                return bytes(val)
            # Some decoders may return int for address; handle conservatively
            if isinstance(val, int):
                return val.to_bytes(20, byteorder="big", signed=False)
            return val

        if typ.startswith("uint") or typ.startswith("int"):
            # int128 can be negative, int24 can be negative; eth_abi handles sign properly.
            if isinstance(val, int):
                return val
            return int(val)

        if typ.startswith("bytes"):
            # bytes32, bytesN, bytes
            if isinstance(val, (bytes, bytearray, memoryview)):
                return bytes(val)
            return val

        # tuples/arrays not expected for this event; return as-is
        return val
