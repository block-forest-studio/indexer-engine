from __future__ import annotations

from typing import Any

from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContract
from web3.exceptions import BadFunctionCallOutput, ContractLogicError

from indexer_engine.app.domain.ports.out import Erc20TokenMetadataFetcher

# Minimal ERC-20 ABI fragments
_ERC20_ABI_STD = [
    {"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "string"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "uint8"}]},
    {"name": "name", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "string"}]},
]

_ERC20_ABI_LEGACY = [
    {"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "bytes32"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "uint256"}]},
    {"name": "name", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"name": "", "type": "bytes32"}]},
]


class Web3Erc20TokenMetadataFetcher(Erc20TokenMetadataFetcher):
    """
    ERC-20 metadata fetcher using AsyncWeb3.

    Fetches:
      - symbol() -> str | None
      - decimals() -> int | None
      - name() -> str | None

    token_address is expected as 20-byte bytes (no 0x prefix).
    """

    def __init__(self, *, w3: AsyncWeb3) -> None:
        self._w3 = w3

    async def fetch(
        self,
        *,
        chain_id: int,
        token_address: bytes,
    ) -> dict[str, Any]:
        _ = chain_id  # intentionally unused (single-chain provider)
        # web3 expects checksum hex string
        addr_hex = self._w3.to_checksum_address("0x" + token_address.hex())

        contract_std: AsyncContract = self._w3.eth.contract(address=addr_hex, abi=_ERC20_ABI_STD)
        contract_legacy: AsyncContract = self._w3.eth.contract(address=addr_hex, abi=_ERC20_ABI_LEGACY)

        # 1) Try standard
        raw_symbol = await self._safe_call(contract_std, "symbol")
        raw_decimals = await self._safe_call(contract_std, "decimals")
        raw_name = await self._safe_call(contract_std, "name")

        symbol = self._normalize_symbol_name(raw_symbol)
        name = self._normalize_symbol_name(raw_name)

        decimals = None
        if isinstance(raw_decimals, int):
            d = int(raw_decimals)
            if 0 <= d <= 255:
                decimals = d

        # 2) Fallback to legacy ONLY for missing fields
        #    (so a mixed token doesn't get overwritten by worse data)
        if symbol is None:
            legacy_symbol = await self._safe_call(contract_legacy, "symbol")
            symbol = self._normalize_symbol_name(legacy_symbol)

        if name is None:
            legacy_name = await self._safe_call(contract_legacy, "name")
            name = self._normalize_symbol_name(legacy_name)

        if decimals is None:
            legacy_decimals = await self._safe_call(contract_legacy, "decimals")
            if isinstance(legacy_decimals, int):
                d = int(legacy_decimals)
                if 0 <= d <= 255:
                    decimals = d

        return {"symbol": symbol, "decimals": decimals, "name": name}

    @staticmethod
    def _normalize_symbol_name(val: Any) -> str | None:
        if val is None:
            return None

        if isinstance(val, str):
            return val.strip() or None

        if isinstance(val, (bytes, bytearray, memoryview)):
            try:
                b = bytes(val)
                return b.rstrip(b"\x00").decode("utf-8").strip() or None
            except Exception:
                return None

        return None

    async def _safe_call(self, contract: AsyncContract, fn_name: str) -> Any | None:
        try:
            fn = getattr(contract.functions, fn_name)
            return await fn().call()
        except (BadFunctionCallOutput, ContractLogicError, ValueError):
            # Non-ERC20, proxy weirdness, revert, or empty response
            return None
        except Exception:
            # Network / timeout / provider error
            return None
