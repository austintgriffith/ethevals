# Wallet test suites as an eval source

Research note, 2026-09-21. Idea from the ethevals call: wallets have spent
years writing tests for exactly the things an agent gets wrong when it builds,
reads or signs a transaction. Mine those suites for evals.

Sixteen repos were cloned and their test files read (not just READMEs). Every
hash below was recomputed or recovered locally where the source had a vector;
truncated values point at the file that holds the full one. Recompute before
shipping an eval; never paste a vector you have not checked with `cast` or viem.

## What the suites contain

Three kinds of material, each mapping to a different eval style.

1. **Signing and serialization vectors.** Raw tx bytes with the fields and
   sender they decode to, typed data with its hash, authorizations with the
   authority they recover to. Sources: viem, ethereumjs, Trust wallet-core,
   Trezor fixtures, MetaMask eth-sig-util, Safe. These become deterministic
   transactions evals with an exact-match grader.
2. **Security rules and attacker payloads.** Rabby's rule engine (about 60
   rules with thresholds), MetaMask test-dapp's malicious requests (literal
   drainer calldata and typed data with a known verdict), revoke.cash's
   trace classifier, Ambire's humanizer, phishing domain lists. These become
   security evals: some deterministic (classify, name the spender), most
   judged (what does signing this do, what should the wallet say).
3. **Wallet behaviour invariants.** What a wallet must accept, reject or
   display: MetaMask core validation, the Wallet Test Framework, Safe error
   codes, 4337 bundler rules, EIP-7702 spec tests. Crisp expected answers,
   good for transactions and building.

## Do these first

Ranked by two things: the answer is checkable, and a strong model plausibly
gets it wrong. None overlap the current 80 evals.

### Transactions

| # | Eval | Expected | Grader | Source |
|---|------|----------|--------|--------|
| 1 | Decode a signed EIP-1559 raw tx: chainId, nonce, to, value, fees, yParity, sender | nonce 785, 2 gwei/2 gwei, 1 ETH to 0x7099…79c8, sender Anvil #0 | exact | viem `utils/transaction/serializeTransaction.test.ts` "eip1559 signed" |
| 2 | Tx type from the first byte: `0x01`, `0x02`, `0x03`, `0x04`, `0xf8…` | 2930, 1559, 4844, 7702, legacy | exact | viem serialize tests |
| 3 | Legacy `v` to chainId and parity: v=0x25, v=173, chain 888 parity 0 | chain 1/0, chain 69/0, v=1811 | exact | ethereumjs `testData/transactionTestEip155VitalikTests.ts`, Trezor `sign_tx.json` "wanchain" |
| 4 | Serialize a 1559 tx with all-zero fields | `0x02dd01808080809470…c88080c0` (zero is `80`, not `00`) | exact | viem "default (all zeros)" |
| 5 | Upfront cost and effective priority fee: maxFee 10, tip 8, gas 100, value 6, baseFee 9 / 2 / 11 | 1006; tip 1; tip 8; invalid | exact | ethereumjs `tx/test/eip1559.spec.ts:21-65` |
| 6 | EIP-7702 authorization hash, then the self-sponsored nonce trap (EOA nonce 5 sends its own type-4 tx) | `keccak(0x05‖rlp([chainId,addr,nonce]))`; tuple nonce 6, sponsor case 5 | exact | viem `hashAuthorization.test.ts`, MetaMask core `eip7702.test.ts:237`, EST `test_set_code_txs.py` |
| 7 | Invalid tuple vs invalid tx: s > N/2, wrong chainId, empty auth list, chainId 0 | tuple skipped and gas still paid; empty list = invalid tx; 0 = any chain | exact | execution-spec-tests `tests/prague/eip7702_set_code_tx/` |
| 8 | Safe tx hash from fields (real Arbitrum Safe, nonce 234, addOwnerWithThreshold) | `0x0cb7250b…25b3`; domain has no name/version; struct hashes `keccak(data)` | exact | pcaversaccio/safe-tx-hashes-util README (verified) |
| 9 | Safe signature type byte and owner ordering | v=0 contract, 1 approved hash, 27/28 ECDSA, 31/32 eth_sign; unsorted owners revert GS026 | exact | safe-smart-account `test/core/Safe.Signatures.spec.ts`, `docs/error_codes.md` |
| 10 | Decode a MultiSend blob (packed `op\|to\|value\|len\|data`) from the Bybit-pattern tx | two inner calls incl. USDC `transfer(…, 800000000)`; operation=1 | exact | safe-tx-hashes-util README l.461-507 |
| 11 | EIP-712 v3 vs v4: missing struct field, `Person[]` array | different hashes; v4 zero-fills, v3 omits; arrays only in v4 | exact | eth-sig-util `sign-typed-data.test.ts:1656`, Trezor `sign_typed_data.json` struct_list_v4 |
| 12 | `personal_sign` of the string `"0xdeadbeef"` vs raw bytes | `0xefedd0a9…` vs the raw hash; hex string is hashed as text | exact | viem `hashMessage.test.ts` |
| 13 | Universal Router `execute` command bytes `0b08000604` with 40 ETH | WRAP_ETH, V2 swap, V3 swap, PAY_PORTION, SWEEP | exact list | Ambire `modules/Uniswap/uniswap.test.ts` |
| 14 | Simulation to balance diff: callTrace + one Transfer log + balanceOf before/after | user change, gas excluded | exact | metamask-extension `test/e2e/tests/confirmations/mocks/simulation.ts` |
| 15 | Who is the spender: user → UniversalRouter → Permit2 → USDC.transferFrom | `approved`, spender = UniversalRouter (Permit2's caller) | exact | revoke.cash `packages/core/lib/transfers/trace-classifier.ts`, fixture `real-universal-router-permit2` |
| 16 | Clear-sign a Uniswap `exactInputSingle` from raw tx using the ERC-7730 descriptor | "Send 0.006471… WETH, Minimum to Receive 13.901216 USDT, fee 0.3 %, Beneficiary 0xEceD…" | exact texts | LedgerHQ/clear-signing-erc7730-registry `registry/uniswap/tests/calldata-UniswapV3Router02.tests.json` |

### Security

| # | Eval | Expected | Grader | Source |
|---|------|----------|--------|--------|
| 17 | Malicious USDC Permit typed data: what does signing do | spender pulls ~1.03M USDC, no tx shown, no gas; deadline already past; spender is an EOA (Rabby rule 1077) | judged | MetaMask test-dapp `src/components/ppom/transactions.js:246`, rabby-security-engine `rules/permit.ts` |
| 18 | Seaport order that gifts six NFTs / 0x ERC721Order with a fixed taker for 0.000042 WETH | offerer receives nothing; recipient is a third party; valid until 2050 | judged | test-dapp `transactions.js:258,270`, Rabby `rules/sellNFT.ts` 1081/1082 |
| 19 | Permit2 PermitBatch: type string, no `version` in domain, one signature covers N tokens until expiration; PermitWitnessTransferFrom with zero recipient | anyone who submits picks the receiver | exact + judged | permit2 `src/libraries/PermitHash.sol`, Ambire `humanizeMessages.test.ts` |
| 20 | SIWE: message says `metamask.badactor.io` but origin is `127.0.0.1:8080`; address 0x0; missing URI; validation order | domain mismatch = phishing; reject; invalid per 4361; unparseable time fails before lifetime checks | exact | test-dapp `signatures/siwe.js`, viem `utils/siwe/validateSiweMessage.test.ts` |
| 21 | Warning bypasses: `verifyingContract` as the decimal `917551056842671309452305380979543736893630245704`, chainId hex-padded, odd-length calldata `0x95ea7b3…` | it is USDC; normalize before matching; odd-length hex is invalid and hides an approve | exact | test-dapp `ppom/bypasses.js` |
| 22 | Typed data with `verifyingContract` = the user's own EOA, or `primaryType: Delegation` with delegator = user | refuse from external origins: 7702 account takeover | exact | MetaMask core `signature-controller/src/utils/validation.test.ts:292-506` |
| 23 | Lookalike domains with allow > block > fuzzy precedence: `opnsea.top`, `opensea.pro`, `metmask.io`, `metamask.money`, `etherid.org`, `opensea.io.` | per list; trailing dot stripped; Levenshtein tolerance 1 | exact | phishing-controller `PhishingDetector.test.ts`, eth-phishing-detect `config.json`, ScamSniffer `blacklist/domains.json` |
| 24 | Safe execTransaction with operation=1 to MultiSend (the Bybit shape): what a signer verifies on device | domain hash, message hash, DelegateCall, the nested calls; plus `refundReceiver` + nonzero `gasPrice` as a drain | judged | safe-tx-hashes-util README, `Safe.Execution.spec.ts` |
| 25 | Rabby thresholds: a "revoke" tx that simulates at 1.4M gas; swap with 22% slippage; unwrap that returns 6% less | warn (revoke should be ~30-50k); danger >20%; danger >5% | exact | rabby-security-engine `rules/revokeToken.ts` 1118, `swap.ts` 1011/1012, `wrap.ts` 1061/1062 |
| 26 | ERC-4626 `deposit(1e6, receiver)` sent with 1 ETH of value | refuse; value on a token-vault call is lost | judged | trezor-firmware `common/tests/fixtures/ethereum/sign_tx_error.json` |
| 27 | Unlimited approval hidden inside a multicall | one warning per distinct spender | count + judged | Ambire `libs/humanizer/erc7730/humanize.test.ts` |
| 28 | EIP-3009 `transferWithAuthorization` moved USDC with no approval; does revoking help | `signature_authorized`; no | exact | revoke.cash fixture `synthetic-eip3009-relayed` |

### Building

| # | Eval | Expected | Grader | Source |
|---|------|----------|--------|--------|
| 29 | EIP-5792: wallet lacks `wallet_sendCalls`, request has `atomic: true` or a non-optional `paymasterService` | must throw, never silently split into N `eth_sendTransaction` | exact | viem `actions/wallet/sendCalls.test.ts:514-590` |
| 30 | `eth_signTransaction` implemented as sign-and-send | wrong: return raw hex, nothing hits the mempool | judged | wallet-test-framework `client/src/tests/eth/signTransaction.ts` |
| 31 | Parse an ERC-6492 wrapped signature; convert 65-byte to EIP-2098 compact | magic suffix, factory, calldata, inner sig; yParity folded into s | exact | viem `serializeErc6492Signature.test.ts`, `signatureToCompactSignature.test.ts` |
| 32 | 4337 validation rules: TIMESTAMP, BALANCE, GAS-then-ADD in `validateUserOp`; unstaked paymaster reading its own storage | banned; ok if staked; GAS only before CALL; STO-031 | exact | eth-infinitism/bundler-spec-tests `tests/single/opbanning`, `bundle/test_storage_rules.py` |
| 33 | v0.8 `userOpHash` and 2D nonce: `getNonce(sender,1)` after one op; fresh key with seq≠0 | EIP-712 domain `ERC4337`/`1`; `(1<<64)+1`; `AA25` | exact | account-abstraction `test/UserOp.ts`, `test/entrypoint.test.ts:403-460` |
| 34 | Coinbase Smart Wallet: `executeWithoutChainIdValidation` with nonce key 0; why ERC-1271 wraps the hash | `InvalidNonceKey`, key must be 8453; replay-safe hash per account | exact + judged | coinbase/smart-wallet `test/CoinbaseSmartWallet/ValidateUserOp.t.sol`, `src/ERC1271.sol` |
| 35 | Which malformed typed data is still signable: unknown type, empty domain, extra untyped field, bad primaryType, `verifyingContract: 1` | only the extra untyped field | exact | test-dapp `signatures/malformed-signatures.js`, eth-sig-util `sign-typed-data.test.ts` |
| 36 | Humanize broadcast errors: nonce too low, replacement underpriced, paymaster fee too low | user action for each | judged | Ambire `errorHumanizer/broadcastErrorhumanizer.test.ts` |
| 37 | Wallet validation table: `{to:"", data:"0x"}`, `{type:"0x2", gasPrice}`, `{gasPrice, maxFeePerGas}` | reject (empty deploy); reject; gasPrice dropped | exact | MetaMask core `transaction-controller/src/utils/validation.test.ts` |

## Source catalog

Reusability: **A** = vectors with exact expected values, **B** = rules with
thresholds or stated expected behaviour, **C** = scenarios, rubric material only.

| Repo | Where to look | What it holds | Reuse |
|------|---------------|---------------|-------|
| wevm/viem | `src/utils/transaction/{serialize,parse}Transaction.test.ts`, `utils/signature/*`, `utils/siwe/*`, `utils/authorization/*`, `actions/wallet/sendCalls.test.ts` | raw hex ↔ fields for every tx type, typed-data hashes, recover, 6492, 2098, SIWE, 5792 | A |
| ethereumjs/ethereumjs-monorepo | `packages/tx/test/{legacy,eip1559,eip7702}.spec.ts`, `testData/` | signed RLP with keys, validation rules, fee arithmetic | A |
| trustwallet/wallet-core | `tests/chains/Ethereum/*.cpp`, `rust/tw_tests/tests/chains/ethereum/*.rs` | full sign vectors: legacy, 1559, 721, 1155, 7702 set-code, 4337 v0.7 UserOp, 191/712, ABI decode to JSON | A |
| trezor/trezor-firmware | `common/tests/fixtures/ethereum/*.json` | real signatures from the public test seed: legacy v per chain, 712 v3 vs v4, 7702 auth, refusals | A |
| MetaMask/eth-sig-util | `src/{personal-sign,sign-typed-data,sign-eip7702-authorization}.test.ts` | personal_sign vectors, V3/V4 differences, 7702 auth hash + sig | A |
| safe-global/safe-smart-account | `test/core/Safe.{Signatures,Execution}.spec.ts`, `test/libraries/MultiSend.spec.ts`, `docs/error_codes.md` | four signature encodings, GS0xx codes, refund math, MultiSend delegatecall | A/B |
| pcaversaccio/safe-tx-hashes-util | `README.md` l.300-507 | real Safe txs with domain/message/safeTxHash and traces, incl. the Bybit shape | A |
| eth-infinitism/account-abstraction | `test/UserOp.ts`, `test/entrypoint.test.ts`, `test/entrypoint-7702.test.ts` | v0.8 userOpHash scheme, 2D nonces, 7702 sender | A |
| eth-infinitism/bundler-spec-tests | `tests/single/opbanning`, `bundle/test_storage_rules.py`, `eip7702/` | the rule matrix (opcode, entity, staked, verdict) | B |
| ethereum/execution-spec-tests | `tests/prague/eip7702_set_code_tx/test_set_code_txs.py` | ~90 tests on nonce, chainId, s-range, chains, precompiles | B |
| MetaMask/core | `packages/transaction-controller/src/utils/*.test.ts`, `signature-controller`, `phishing-controller` | validation rules, gas buffers, tx type detection, panic codes, phishing precedence | B |
| MetaMask/test-dapp | `src/components/ppom/*.js`, `signatures/*.js` | attacker payloads with known verdicts, warning bypasses, SIWE variants | A/B |
| MetaMask/metamask-extension | `test/e2e/tests/{ppom,confirmations}/` | Blockaid verdict shapes, simulation fixtures, enforced simulations | C |
| RabbyHub/rabby-security-engine | `src/rules/*.ts` | ~60 rules with ids, thresholds and descriptions | B |
| AmbireTech/ambire-common | `src/libs/humanizer/**/*.test.ts`, `erc7730/` | calldata and typed data → English, with expected phrases | A |
| RevokeCash/revoke.cash | `apps/web/test/transfer-extraction.test.ts`, `fixtures/transfer-traces.json`, `packages/core/lib/transfers/trace-classifier.ts` | trace + logs → transfer class and spender; 4 real mainnet txs | A |
| LedgerHQ/clear-signing-erc7730-registry | `registry/*/tests/*.tests.json` | raw tx → expected display texts | A |
| LedgerHQ/app-ethereum | `tests/ragger/test_{eip7702,gcs,blind_sign,trusted_name}.py` | delegate whitelist, blind-sign gating, nested Safe display | C |
| Uniswap/permit2 | `src/libraries/PermitHash.sol`, `src/EIP712.sol` | exact type strings; domain has no version | A |
| coinbase/smart-wallet | `test/CoinbaseSmartWallet/*.t.sol`, `test/ERC1271.t.sol` | replayable nonce key, replay-safe 1271 | B |
| wallet-test-framework/framework | `client/src/tests/eth/*.ts` | one spec per RPC method: what the prompt must show, what must not happen | C |
| MetaMask/eth-phishing-detect, scamsniffer/scam-database | `src/config.json`; `blacklist/{domains,address}.json` | 100k+ / 355k domains, 2.5k drainer addresses | A |

Not reached: Rainbow (one trivial test), Uniswap wallet, Zerion, Frame, Taho,
Enkrypt, Phantom, OKX, Keystone, GridPlus. Blockaid docs are login-gated.

## Broader ideas the suites suggest

- **Signature format zoo.** 65-byte, 2098 compact, 6492 wrapped, 1271
  on-chain, Safe's four encodings. Identify by length and suffix, say who
  verifies it and how. Cuts across transactions and building.
- **What a wallet must show.** Per RPC method (WTF) and per tx type: for a
  type-4 tx the delegate, chainId 0 meaning every chain, the nonce. For a
  Safe tx the three hashes and the operation. For a Permit the spender, amount
  and deadline in human units. ERC-7730 makes this gradeable.
- **Simulation is not truth.** revoke.cash fixtures for Rootstock and Gnosis
  show tracers propagating logs from reverted frames. MetaMask's enforced
  simulations bind the on-chain result to the preview. Good judged evals on
  when to trust a preview.
- **Address and site trust signals.** First-time recipient, CEX hot wallet
  vs deposit address, recipient is a token contract, spender is an EOA,
  contract deployed under 3 days ago, site popularity zero. Rank the signals.
- **Wallet refusals as a design eval.** Trezor and Ledger refuse chainId 0
  authorizations and unknown delegates; Rabby fails closed when a rule
  errors. Ask the model to design the signing pipeline and check it fails
  closed.
- **Derivation paths.** Same seed, Ledger Live path vs BIP-44 vs per-chain
  coin type: why the addresses differ.

## Turning these into evals

- Quizzes end with `Answer: …` and use the `exact` grader; the agent may run
  `cast`, viem or Python, so hash and signature evals are fair and still
  discriminate (transactions-03/04/19 already fail on arithmetic).
- Compute every expected value locally with two independent tools before
  committing. Keep expected hashes in the yaml as `Answer: 0x…` lines (the
  port script pattern) so gitleaks does not flag them; never copy a fixture
  private key into the repo.
- For judged evals, lift the rubric from the source: Rabby rule
  `descriptions`, Ambire `expectedTexts`, Blockaid `reason` strings.
- Add via `tools/gen_authored.py`, re-run, self-test, then `--resume` every
  existing card.
