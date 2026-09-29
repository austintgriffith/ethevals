# JSON-RPC as an eval source

Research note, 2026-09-29. The four pillars had no eval for the execution-layer
JSON-RPC contract. Agents that build wallets, indexers and backends talk to a
node all day. The mistakes are specific: which block tag is safe to credit on,
what an `eth_getLogs` error means, what `eth_simulateV1` does with fields you
leave out, what a 7702 account looks like over RPC.

## Where the answers come from

- **ethereum/execution-apis fixtures.** `tests/<method>/*.io` holds recorded
  request and response pairs. A fixture without a `speconly` comment is
  compared exactly against every client by the Hive `rpc-compat` simulator, so
  its response is what geth, Reth, Nethermind, Besu and Erigon return. The
  generator uses only those fixtures. `speconly` fixtures are checked for
  schema only and are not used.
- **EIP formulas.** rpc-08 (EIP-4844 with EIP-7918), rpc-09 (EIP-1559) and
  rpc-12 (EIP-7702) are computed in `tools/gen_rpc.py`. The code was checked
  against go-ethereum `consensus/misc/eip4844`, `consensus/misc/eip1559` and
  `core/state_transition.go`. These are consensus rules, so every client must
  agree.
- **JSON-RPC 2.0.** rpc-01 follows the JSON-RPC 2.0 specification text.
- **Judged evals.** rpc-15 to rpc-25 are scenarios with written conditions.
  Each rubric was checked with the default judge: a correct answer passes, and
  a common wrong answer fails.

## The evals

| Eval | Tests | Ground truth |
|---|---|---|
| rpc-01 | Batch edge cases: `id: null` is not a notification; `[]` returns one error object; an all-notification batch returns nothing | JSON-RPC 2.0 |
| rpc-02 | An unset simulated timestamp is parent + 12, and timestamps must strictly increase | `ethSimulate-block-timestamp-auto-increment.io` |
| rpc-03 | A jump in block number is filled with empty blocks | `ethSimulate-blocknumber-increment.io` |
| rpc-04 | Topic filters match by position; `null` is a wildcard | `topic-null-wildcard.io` |
| rpc-05 | `movePrecompileToAddress` leaves the old address empty | `ethSimulate-move-ecrecover-and-call.io` |
| rpc-06 | A block past the head is `null`; a log range past the head is `-32602`, never clamped | `src/eth/filter.yaml`, `get-block-notfound.io` |
| rpc-07 | `eth_feeHistory` rewards are weighted by gas used over effective tips | `src/eth/fee_market.yaml`, geth `feehistory.go` |
| rpc-08 | Below the reserve price, excess blob gas does not fall (EIP-7918) | EIP-7918, `eth_config/get-config.io` |
| rpc-09 | EIP-1559 is integer math: +1 wei minimum, small decreases round to 0 | EIP-1559 |
| rpc-10 | A `gasLimit` override carries to the next simulated block; a call without `gas` gets what is left | `ethSimulate-run-out-of-gas-in-block-38015.io` |
| rpc-11 | A delegated EOA's code is the 23-byte designator | `get-code-eip7702-delegation.io` |
| rpc-12 | Five authorization tuples against the running nonce; chain ID 0; address 0 clears | EIP-7702 |
| rpc-13 | `traceTransfers` reports ETH moves as logs from `0xeeee…eeee` | `ethSimulate-eth-send-should-produce-logs.io` |
| rpc-14 | Without validation, nonce and fee checks are skipped, but balance and intrinsic gas are not | six `ethSimulate-*` fixtures |
| rpc-15 to rpc-25 | Block tags for deposits, removed logs, estimateGas reverts, what a tx hash promises, nonces behind a load balancer, 7702-delegated EOAs, log scans, consistent reads (EIP-1898), multi-call previews, `eth_getProof`, fee fields | judged |

## Measured difficulty

Closed-book runs of the rpc pillar, one run each, on 2026-09-29. The executor
ran under `sandbox-exec` with reads of the local client and spec checkouts
denied, and with WebFetch and WebSearch disabled.

| Model | rpc |
|---|---|
| Haiku 4.5 | 3/25 |
| Sonnet 5.5 | 22/25 |
| GPT-6 Astra (Codex) | 22/25 |
| Opus 5.5 | 23/25 |
| Fable 5.1 | 25/25 |

Misses by the larger models: rpc-01 (Opus: counted 4 responses, though its own
counts add up to 5), rpc-04 (Opus), rpc-06 (Sonnet: said geth clamps the
range), rpc-14 (Sonnet), rpc-15 and rpc-20 (GPT-6 Astra), rpc-25 (Sonnet,
GPT-6 Astra). After these runs, the prompts of rpc-02, 03, 10 and 14 were
reworded (the answers did not change), and the rubrics of rpc-19, 20 and 22
were widened after review.

With tool access, a model can read the answers from the public fixtures. In
an open run on a machine with an execution-apis checkout, Opus quoted
`tests/eth_getLogs/filter-error-future-block-range.io`. Run closed-book to
measure knowledge.

## Spec and client conflicts found

These are not in the evals, or the evals are worded around them. Each one is
worth an issue or a fixture upstream.

1. **eth_getLogs, a filter longer than the log's topics.** `[T, null]` against
   a log with only `[T]`: Reth matches; geth, Nethermind, Besu, Erigon, ethrex
   and Nimbus do not. The spec is silent and no fixture covers it. Excluded.
2. **eth_simulateV1 timestamps.** `src/schemas/execute.yaml` says an unset
   time increments by one and may stay constant. The simulate notes, every
   client and the Hive fixtures use +12 and a strict increase. rpc-02 and
   rpc-03 ask what a node that passes the fixtures returns.
3. **eth_simulateV1 default gasLimit.** `docs-api/docs/ethsimulatev1-notes.mdx`
   says the base block's gasLimit. Every client carries an override into the
   next simulated block, as the fixture expects. rpc-10 is worded the same way.
4. **Besu, value above balance in eth_simulateV1.** Besu returns `-32603`;
   the fixture and the spec error table expect `-38014`.
