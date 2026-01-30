from __future__ import annotations

from typing import Protocol, Any


class EvmEventLogsIndexer(Protocol):
    """
    Port for indexing EVM event logs into the staging layer.

    Implementations are responsible for loading data from raw.* tables
    into staging.evm_event_logs in an idempotent, set-based way.
    """

    async def index_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        ...


class AnalyticsEvmEventsIndexer(Protocol):
    """
    Port for indexing normalized EVM events into the analytics layer.

    Implementations are responsible for transforming rows from
    staging.evm_event_logs into analytics.evm_events in an idempotent,
    set-based way.

    The analytics layer represents a curated, query-optimized view of on-chain
    activity.
    """
    async def index_events_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None:
        ...


class UniswapV4WalletSwapsIndexer(Protocol):
    """
    Port for indexing Uniswap v4 wallet swap projections into the domain layer.
    """
    async def index_swaps_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None: ...


class EvmEventDecoder(Protocol):
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
        Decode an EVM log (topics + data) into a dict of typed fields.

        Return:
          - dict[str, Any] for decoded event fields
          - None if the log is not decodable / not the expected event
        """
        ...


class UniswapV4PoolsIndexer(Protocol):
    """
    Port for indexing Uniswap v4 pools registry into the domain layer.

    Typically built from PoolManager Initialize events and persisted into
    domain.uniswap_v4_pools in an idempotent way.
    """

    async def index_pools_for_block_range(
        self,
        *,
        chain_id: int,
        from_block: int,
        to_block: int,
    ) -> None: ...


class TokensIndexer(Protocol):
    """
    Port for indexing ERC-20 token metadata into the domain layer.

    Implementations are responsible for:
    - discovering token addresses (e.g. from domain.uniswap_v4_pools),
    - fetching on-chain metadata via eth_call (symbol, decimals, name),
    - upserting rows into domain.tokens.

    This is a reference-data indexer, not event-based.
    """

    async def index_tokens(
        self,
        *,
        chain_id: int,
        limit: int | None = None,
    ) -> None: ...


class Erc20TokenMetadataFetcher(Protocol):
    """
    Low-level dependency used by the tokens adapter.

    Implementations should perform eth_call against the ERC-20 contract and return:
      - symbol (str | None)
      - decimals (int | None)
      - name (str | None)

    token_address is 20-byte bytes (no 0x prefix).
    """

    async def fetch(
        self,
        *,
        chain_id: int,
        token_address: bytes,
    ) -> dict[str, Any]:
        ...