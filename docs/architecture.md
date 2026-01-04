## staging.evm_event_logs – canonical EVM event logs

`staging.evm_event_logs` is the canonical staging table for EVM event logs.
Each row represents a single log entry emitted by a smart contract, enriched with generic (ABI-agnostic) transaction and receipt context.

This table is the main bridge between raw.* and higher-level, protocol-specific/indexer logic.
It is designed to be stable, typed, and efficient for querying, while still remaining neutral with respect to concrete protocols (Uniswap, Aave, etc.).

### Purpose
- Provide a single, curated source of truth for EVM logs across all supported protocols/contracts.
- Avoid repeatedly joining raw.logs, raw.transactions, and raw.receipts in downstream logic.
- Expose generic transaction/receipt context (from/to, value, gas, status, etc.) without any ABI decoding.
- Optimise for common lookup patterns used by the API and domain services:
    - by contract address + event type (topic0) in a block range 
    - by transaction hash.

### Table schema

Schema: staging
Table: evm_event_logs

Primary key (natural, canonical):
- PRIMARY KEY (chain_id, block_number, log_index)

Columns:
- Block / chain context
    - chain_id – integer
    Chain identifier (e.g. 1 = Ethereum mainnet).

    - block_number – bigint
    Block number in which the log was emitted.

    - block_timestamp – timestamptz
    Timestamp of the block that included the log (UTC, timezone-aware).
- Transaction identity
    - transaction_hash – bytea
    Hash of the transaction that emitted the log.

    - transaction_index – integer
    Index of the transaction within the block (0-based).

    - log_index – integer
    Index of the log within the block (0-based, deterministic ordering).
- Transaction context (generic, ABI-agnostic)
    - tx_from – bytea
    Sender address of the transaction.

    - tx_to – bytea NULL
    Recipient address; NULL for contract creations.

    - tx_value – numeric
    Transaction value in native units (e.g. wei).

    - tx_type – smallint NULL
    Transaction type (e.g. 0 = legacy, 2 = EIP-1559); may be NULL on older chains.

    - tx_status – smallint NULL
    Receipt status (1 = success, 0 = failure, NULL = not available).

    - tx_gas_used – bigint NULL
    Gas used by this transaction.

    - tx_cumulative_gas_used – bigint NULL
    Cumulative gas used up to and including this transaction in the block.

    - tx_effective_gas_price – numeric NULL
    Effective gas price from receipt (EIP-1559 aware).
- Log payload (raw EVM log fields)
    - address – bytea
    Contract address that emitted the log.

    - topic0 – bytea NULL
    keccak256 hash of the event signature.

    - topic1 – bytea NULL
    First indexed event argument.

    - topic2 – bytea NULL
    Second indexed event argument.

    - topic3 – bytea NULL
    Third indexed event argument.

    - data – bytea
    ABI-encoded non-indexed event arguments.

All blockchain identifiers (addresses, hashes, topics) are stored as BYTEA to preserve canonical binary form and avoid formatting/normalisation concerns at this layer. Any hex/string formatting and ABI-level semantics are intentionally deferred to higher-level domain/indexing logic.

### Indexes
The table is indexed for the most common access patterns:
- By contract + event + block range:

```sql
INDEX ix_logs_chain_address_topic0_block
  ON staging.evm_event_logs (chain_id, address, topic0, block_number);
```

- By transaction hash:

```sql
INDEX ix_logs_chain_txhash
  ON staging.evm_event_logs (chain_id, transaction_hash);
```

### Source data and transformation

`staging.evm_event_logs` is populated from the RAW layer:
- raw.logs
- raw.transactions
- raw.receipts

The canonical mapping (per row) is:
- From raw.logs:
    - chain_id
    - block_number
    - transaction_hash
    - log_index
    - address
    - topic0..topic3
    - data
- From raw.transactions (joined by (chain_id, hash = transaction_hash)):
    - "from" → tx_from
    - "to" → tx_to
    - value → tx_value
    - "type" → tx_type
    - transaction_index → transaction_index
- From raw.receipts (joined by (chain_id, transaction_hash)):
    - status → tx_status
    - gas_used → tx_gas_used
    - cumulative_gas_used → tx_cumulative_gas_used
    - effective_gas_price → tx_effective_gas_price
    - block_timestamp → block_timestamp

### Canonical load pattern (conceptual):
```sql
INSERT INTO staging.evm_event_logs (
    chain_id,
    block_number,
    block_timestamp,
    transaction_hash,
    transaction_index,
    log_index,
    tx_from,
    tx_to,
    tx_value,
    tx_type,
    tx_status,
    tx_gas_used,
    tx_cumulative_gas_used,
    tx_effective_gas_price,
    address,
    topic0,
    topic1,
    topic2,
    topic3,
    data
)
SELECT
    l.chain_id,
    l.block_number,
    r.block_timestamp,
    l.transaction_hash,
    t.transaction_index,
    l.log_index,
    t."from"       AS tx_from,
    t."to"         AS tx_to,
    t.value        AS tx_value,
    t."type"       AS tx_type,
    r.status       AS tx_status,
    r.gas_used     AS tx_gas_used,
    r.cumulative_gas_used      AS tx_cumulative_gas_used,
    r.effective_gas_price      AS tx_effective_gas_price,
    l.address,
    l.topic0,
    l.topic1,
    l.topic2,
    l.topic3,
    l.data
FROM raw.logs l
JOIN raw.transactions t
  ON t.chain_id = l.chain_id
 AND t.hash     = l.transaction_hash
JOIN raw.receipts r
  ON r.chain_id         = l.chain_id
 AND r.transaction_hash = l.transaction_hash
WHERE l.chain_id = :chain_id
  AND l.block_number BETWEEN :from_block AND :to_block
ON CONFLICT DO NOTHING;
```

The actual implementation in indexer-engine uses this pattern as a single, set-based operation (INSERT … SELECT … ON CONFLICT DO NOTHING) to keep the process idempotent and efficient for large block ranges.