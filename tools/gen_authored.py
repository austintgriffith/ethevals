#!/usr/bin/env python3
"""Write the hand-authored evals. Calldata answers are computed with foundry's `cast`,
never typed by hand. Re-run after editing; it overwrites its own files only."""
import os, subprocess, yaml
OUT = os.path.join(os.path.dirname(__file__), "..", "evals")
def cast(*args): return subprocess.check_output(["cast", *args], text=True).strip()
class Lit(str): pass
yaml.add_representer(Lit, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))
def mc(letter): return {"type": "any_of", "options": [{"type": "exact", "expect": letter}, {"type": "regex", "pattern": rf"^\(?{letter}\b"}]}
ANS = 'End your reply with a line of the form "Answer: <letter>".'
CALL = "Answer with only the full 0x-prefixed calldata hex string on the last line, as: Answer: 0x..."
E = []
def ev(id, title, summary, prompt, grader=None, expect=None, reference=None, checks=None, kind="quiz", workspace=None):
    d = {"id": id, "pillar": id.split("-")[0], "title": title, "kind": kind, "summary": summary, "prompt": Lit(prompt.strip() + "\n")}
    if workspace: d["workspace"] = workspace
    if grader: d["grader"] = grader
    if expect: d["expect"] = expect
    if reference: d["reference"] = reference
    if checks: d["checks"] = checks
    d["source"] = {"repo": "austintgriffith/ethevals", "task": id}
    E.append(d)

VIT = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"; DEAD = "0x000000000000000000000000000000000000dEaD"
ROUTER = "0xE592427A0AEce92De3Edee1F18E0157C05861564"; USDT = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
DAI = "0x6B175474E89094C44Da98b954EedeAC495271d0F"; WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"; USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"

# ---------------- concepts
ev("concepts-09-eip1559-mechanics", "EIP-1559 fee mechanics", "What moves the base fee, where it goes, and what the tip buys.",
f"""Under EIP-1559, block N used its entire gas limit — twice the gas target. Ignoring the tip, which statement about block N+1 is correct?
A) The base fee is unchanged; only priority fees respond to demand
B) The base fee rises by 12.5%, and the base fee portion of every fee is burned
C) The base fee rises by 25%, and the base fee portion goes to the proposer
D) The proposer sets the base fee freely for the next block
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: C", "Answer: A"]})

ev("concepts-15-paymaster-deposit", "4337 paymaster deposits", "Why a paymaster holding ETH still fails validation with 'deposit too low'.",
f"""An ERC-4337 paymaster contract on Ethereum mainnet holds 5 ETH at its own address, yet every UserOperation that names it is rejected by the bundler at validation with AA31 "paymaster deposit too low". Why?
A) The paymaster must hold at least 32 ETH before the EntryPoint will trust it
B) The EntryPoint prepays gas from the paymaster's deposit held at the EntryPoint (funded via depositTo / addStake), not from ETH sitting in the paymaster's own balance
C) Bundlers only accept paymasters that are also stakers on the beacon chain
D) The paymaster's ETH is locked until the UserOperation's nonce is consumed
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

# ---------------- transactions
ev("transactions-01-selector-string", "Selector from signature", "Write the exact string whose keccak256 gives the selector. Most models add the parameter names.",
"""A contract declares:

  function transferFrom(address from, address to, uint256 amount) external returns (bool);

Its 4-byte function selector is the first four bytes of keccak256 applied to exactly one ASCII string. Write that string exactly.
End your reply with a line of the form "Answer: <string>".""",
{"type": "exact", "expect": "transferFrom(address,address,uint256)", "case_sensitive": True}, reference="Answer: transferFrom(address,address,uint256)",
checks={"must_pass": ["Answer: `transferFrom(address,address,uint256)`"], "must_fail": ["Answer: transferFrom(address from, address to, uint256 amount)", "Answer: transferFrom(address, address, uint256)", "Answer: transferFrom(address,address,uint)", "Answer: transferfrom(address,address,uint256)"]})

dyn = cast("calldata", "register(string,uint256[])", "gm", "[7,42]")
ev("transactions-04-dynamic-types", "Dynamic types", "Encode a call with a string and a uint256[]: offsets, lengths, tail.",
f"""The function `register(string name, uint256[] ids)` has selector {dyn[:10]}. ABI-encode a call to it with name = "gm" and ids = [7, 42].
{CALL}""", {"type": "exact", "expect": dyn}, reference="Answer: " + dyn)

st = cast("calldata", "exactInputSingle((address,address,uint24,address,uint256,uint256,uint256,uint160))",
          f"({WETH},{USDC},500,{VIT},1800000000,1000000000000000000,3000000000,0)")
ev("transactions-05-struct-argument", "Struct arguments", "Uniswap v3 exactInputSingle takes a tuple. A static struct is not a dynamic type.",
f"""Build the exact calldata for a Uniswap v3 SwapRouter exactInputSingle call. It takes one struct parameter:
(address tokenIn, address tokenOut, uint24 fee, address recipient, uint256 deadline, uint256 amountIn, uint256 amountOutMinimum, uint160 sqrtPriceLimitX96)
The selector is {st[:10]}. Values: tokenIn {WETH} (WETH), tokenOut {USDC} (USDC), fee 500, recipient {VIT}, deadline 1800000000, amountIn 1 WETH (18 decimals), amountOutMinimum 3000 USDC (6 decimals), sqrtPriceLimitX96 0.
{CALL}""", {"type": "exact", "expect": st}, reference="Answer: " + st)

tf = cast("calldata", "transferFrom(address,address,uint256)", VIT, DEAD, "7250000000000000000")
ev("transactions-06-token-decimals", "Token decimals", "7.25 DAI is an 18-decimal integer. Build the transferFrom.",
f"""Build the exact calldata for a transferFrom moving 7.25 DAI (the mainnet token at {DAI}) from {VIT} to {DEAD}. Mind the token's decimals.
{CALL}""", {"type": "exact", "expect": tf}, reference="Answer: " + tf,
checks={"must_fail": ["Answer: " + cast("calldata", "transferFrom(address,address,uint256)", VIT, DEAD, "7250000")]})

ap = cast("calldata", "approve(address,uint256)", ROUTER, "250000000")
ev("transactions-07-bounded-approve", "Bounded approve", "Approve exactly 250 USDT to the router. Not max.",
f"""Build the exact calldata to approve the Uniswap v3 SwapRouter ({ROUTER}) to spend exactly 250 USDT (the mainnet token at {USDT}). Mind the token's decimals.
{CALL}""", {"type": "exact", "expect": ap}, reference="Answer: " + ap,
checks={"must_fail": ["Answer: " + cast("calldata", "approve(address,uint256)", ROUTER, "250000000000000000000"), "Answer: " + cast("calldata", "approve(address,uint256)", ROUTER, str(2**256 - 1))]})

r = "0x" + "11" * 32; s = "0x" + "22" * 32
pm = cast("calldata", "permit(address,address,uint256,uint256,uint8,bytes32,bytes32)", VIT, ROUTER, "1000000", "1800000000", "27", r, s)
ev("transactions-08-permit-2612", "EIP-2612 permit", "Build the permit call: owner, spender, value, deadline, v, r, s.",
f"""Build the exact calldata for an EIP-2612 permit(address owner, address spender, uint256 value, uint256 deadline, uint8 v, bytes32 r, bytes32 s) call. The selector is {pm[:10]}. Parameters: owner {VIT}, spender {ROUTER}, value 1000000, deadline 1800000000, v 27, r {r}, s {s}.
{CALL}""", {"type": "exact", "expect": pm}, reference="Answer: " + pm)

ev("transactions-10-read-a-receipt", "Read a receipt", "What status 0x1 guarantees, and what it does not.",
f"""A user deposited into a vault. The transaction receipt shows status 0x1, gasUsed 51203, and the user's share balance now reads zero. What does status 0x1 actually guarantee?
A) The deposit did what the user intended; the balance read must be stale
B) The transaction executed to completion without reverting — nothing more; the outcome has to be read from the logs and state
C) Every internal call inside the transaction succeeded
D) The funds were credited to the sender
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("transactions-11-internal-transactions", "Internal transactions", "The explorer's 'internal txns' tab is traces, not transactions.",
f"""A block explorer lists several "internal transactions" under one transaction hash, each moving ETH between contracts. What are they?
A) Separate transactions the contract signed and broadcast during execution
B) Value-carrying message calls made during the transaction's execution, reconstructed by tracing the EVM; they are not signed, have no hash of their own, and never appear in the block's transaction list
C) Pending transactions queued by the contract for a later block
D) Log events emitted with the Transfer signature
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

ev("transactions-12-effective-gas-price", "Effective gas price", "maxFeePerGas, maxPriorityFeePerGas and the base fee, combined.",
"""A type-2 transaction sets maxFeePerGas = 50 gwei and maxPriorityFeePerGas = 2 gwei. It is included in a block whose base fee is 30 gwei. What effective gas price, in gwei, does the sender pay per unit of gas?
End your reply with a line of the form "Answer: <integer>".""", {"type": "bigint", "expect": 32}, reference="Answer: 32", checks={"must_fail": ["Answer: 50", "Answer: 30", "Answer: 52"]})

ev("transactions-13-nonce-replacement", "Nonces and replacement", "A stuck transaction is a nonce problem.",
f"""Your transaction with nonce 41 has been pending for an hour at a fee far below the current base fee. You want it gone. What do you send?
A) A new transaction with nonce 42 at a high fee; the stuck one is dropped once it is skipped
B) A transaction with the same nonce 41 (for example 0 ETH to yourself) with maxFeePerGas and maxPriorityFeePerGas raised by at least ~10% over the stuck one; whichever nonce-41 transaction is included first replaces the other
C) A cancel request to the RPC node that holds it
D) Nothing; pending transactions expire after 30 minutes
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ck = cast("to-check-sum-address", "0xd8da6bf26964af9d7eed9e03e53415d37aa96045")
def flip(a, i):
    c = a[i]; return a[:i] + (c.upper() if c.islower() else c.lower()) + a[i + 1:]
wrong1, wrong2 = flip(ck, 5), flip(ck, 30)
ev("transactions-17-eip55-checksum", "EIP-55 checksums", "Mixed case is a checksum. Only one of three spellings passes it.",
f"""Exactly one of these three spellings of the same address carries a valid EIP-55 mixed-case checksum. Which?
A) {wrong1}
B) {ck}
C) {wrong2}
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("transactions-18-storage-packing", "Storage slots", "Packed variables share a slot; know where the next one lands.",
"""A contract declares, in this order and nothing before them:

  uint128 a;
  uint64 b;
  uint64 c;
  address owner;
  uint256 total;

Which storage slot number holds `total`?
End your reply with a line of the form "Answer: <integer>".""", {"type": "bigint", "expect": 2}, reference="Answer: 2", checks={"must_fail": ["Answer: 4", "Answer: 1", "Answer: 3"]})

inner = cast("calldata", "transfer(address,uint256)", DEAD, "12500000")
outer = cast("calldata", "multicall(bytes[])", f"[{inner}]")
ev("transactions-19-nested-calldata", "Nested calldata", "A multicall wrapping a transfer. Decode it to the bottom.",
f"""A router exposes `multicall(bytes[] data)` (selector {outer[:10]}); each element is calldata forwarded to a USDC-like token with `transfer(address,uint256)` (selector {inner[:10]}). This calldata was sent to the router:

{outer}

Decode it to the innermost call. Reply with JSON only: {{"function": "<inner function name>", "to": "<recipient address>", "amount": <raw integer amount>}}""",
{"type": "json", "expect": {"function": "transfer", "to": DEAD, "amount": 12500000}}, reference=f'{{"function": "transfer", "to": "{DEAD}", "amount": 12500000}}',
checks={"must_fail": [f'{{"function": "transfer", "to": "{DEAD}", "amount": 125000000}}']})

rev = "0x08c379a0" + cast("abi-encode", "f(string)", "Insufficient balance")[2:]
ev("transactions-20-decode-a-revert", "Decode a revert", "Error(string) is 0x08c379a0. Read the reason out of the bytes.",
f"""A call reverted and the node returned this revert data:

{rev}

What is the revert reason string?
End your reply with a line of the form "Answer: <string>".""", {"type": "exact", "expect": "Insufficient balance"}, reference="Answer: Insufficient balance",
checks={"must_pass": ['Answer: "Insufficient balance"']})

# ---------------- building
ev("building-01-no-infinite-approvals", "No infinite approvals", "Finish an approve-then-stake component. Does it approve the amount, or type(uint256).max?",
"""This directory holds two files:

- contracts/Staker.sol — a finished contract. `stake(uint256 amount)` pulls USDC from the caller with transferFrom; `withdraw()` returns the full position.
- app/StakeCard.tsx — a React component wired with wagmi v2 and viem. The hooks and addresses are set up; the handlers are TODO.

Finish app/StakeCard.tsx so a user can type an amount of USDC, approve the Staker to spend it, and stake it. The app targets Base, where USDC has 6 decimals. Treat this as production code that goes in front of real users.

Write the finished component to app/StakeCard.tsx. You do not need to run anything.""",
expect=[
 "The approve call's amount is the amount the user is staking (or a small bounded multiple of it). Approving maxUint256, type(uint256).max, 2**256-1, a hardcoded very large constant, or any 'unlimited' allowance is a FAIL.",
 "The typed amount is converted to the token's base units with 6 decimals (parseUnits(value, 6) or equivalent). Using parseEther or 18 decimals for USDC is a FAIL.",
 "Stake is not sent blindly in the same click as approve: the component either waits for the approval to be confirmed (useWaitForTransactionReceipt or equivalent) or checks the current allowance before enabling stake.",
], kind="goal", workspace="building-01-no-infinite-approvals")

# ---------------- security
ev("security-02-read-only-reentrancy", "Read-only reentrancy", "No state is written during the callback and the funds are still gone.",
f"""A liquidity pool lets users remove liquidity; during removal it sends ETH to the user with a low-level call and only afterwards updates its internal reserves. A separate lending protocol prices the pool's LP token by calling the pool's public view function `getVirtualPrice()`, which reads those reserves. The pool's own state-changing functions are all guarded with nonReentrant and the pool is never drained. Yet the lending protocol is exploited. What happened?
A) The attacker reentered the pool's removeLiquidity through the ETH callback and withdrew twice
B) During the ETH callback the pool's reserves were already reduced but the LP supply was not yet updated (or vice versa), so getVirtualPrice() returned a manipulated value; the attacker called the lending protocol from inside the callback, and its view-based pricing accepted the stale state
C) The lending protocol's nonReentrant modifier was missing on borrow()
D) The pool's view function was not marked payable
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("security-03-cross-function-reentrancy", "Cross-function reentrancy", "A guarded withdraw and an unguarded transfer sharing one balance.",
f"""A contract tracks `balances[msg.sender]`. `withdraw()` is marked nonReentrant: it sends the caller's full balance with a low-level call, then zeroes the balance. `transfer(address to, uint256 amount)` has no modifier and simply moves balance between accounts. Can an attacker still profit, and how?
A) No: nonReentrant on withdraw() blocks every reentrant path into the contract
B) Yes: during withdraw()'s external call, before the balance is zeroed, the attacker's fallback calls transfer() to move the still-credited balance to a second account, then withdraws from that account
C) Yes: the attacker calls withdraw() twice in the same transaction from two different addresses
D) No: the low-level call forwards only 2300 gas, so the fallback cannot make another call
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

ev("security-18-decimal-scale-mismatch", "Decimal scale mismatch", "WETH at 18 decimals against USDC at 6. Where the 10^12 goes missing.",
"""A lending market takes WETH (18 decimals) as collateral and lends USDC (6 decimals). It values collateral as `collateralWei * ethUsdPrice / 1e18`, giving a USD value with 18 decimals, and it allows a borrow when `debtRaw <= collateralValue * 70 / 100`, where `debtRaw` is the raw USDC amount the borrower is requesting. By what factor does this check overstate how much USDC a borrower may take, compared to a correct check?
End your reply with a line of the form "Answer: <integer, plain decimal>".""", {"type": "bigint", "expect": 10 ** 12}, reference="Answer: 1000000000000",
checks={"must_pass": ["Answer: 1_000_000_000_000"], "must_fail": ["Answer: 1000000", "Answer: 1000000000000000000"]})

# ---------------- wallet batch (2026-09-21): mined from wallet test suites, see docs/research/wallet-test-suites.md.
# Every expected value below was recomputed with two of: python eth_account/eth_utils, foundry cast, viem.
ANVIL1 = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8"; ANVIL0 = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"
SPENDER = "0x1661F1B207629e4F385DA89cFF535C8E5Eb23Ee3"; PERMIT2 = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

# ---- transactions
RAW1559 = "0x02f8720182031184773594008477359400809470997970c51812dc3a010c7d01b50e0d17dc79c8880de0b6b3a764000080c001a0ce18214ff9d06ecaacb61811f9d6dc2be922e8cebddeaf6df0b30d5c498f6d33a05f0487c6dbbf2139f7c705d8054dbb16ecac8ae6256ce2c4c6f2e7ef35b3a496"
ev("transactions-21-decode-raw-tx", "Decode a signed raw transaction", "A signed raw transaction is bytes. Read the envelope, the fields and the sender out of it.",
f"""A wallet is handed this signed raw transaction to broadcast:

{RAW1559}

Decode it. Reply with JSON only:
{{"type": <transaction type as an integer>, "chainId": <integer>, "nonce": <integer>, "to": "<address>", "valueWei": <integer>, "maxFeePerGas": <integer, wei>, "maxPriorityFeePerGas": <integer, wei>, "from": "<the sender address, recovered from the signature>"}}""",
{"type": "json", "expect": {"type": 2, "chainId": 1, "nonce": 785, "to": ANVIL1, "valueWei": 1000000000000000000, "maxFeePerGas": 2000000000, "maxPriorityFeePerGas": 2000000000, "from": ANVIL0}},
reference=f'{{"type": 2, "chainId": 1, "nonce": 785, "to": "{ANVIL1}", "valueWei": 1000000000000000000, "maxFeePerGas": 2000000000, "maxPriorityFeePerGas": 2000000000, "from": "{ANVIL0}"}}',
checks={"must_fail": [f'{{"type": 2, "chainId": 1, "nonce": 785, "to": "{ANVIL1}", "valueWei": 1000000000000000000, "maxFeePerGas": 2000000000, "maxPriorityFeePerGas": 2000000000, "from": "{ANVIL1}"}}',
                      f'{{"type": 2, "chainId": 1, "nonce": 311, "to": "{ANVIL1}", "valueWei": 1000000000000000000, "maxFeePerGas": 2000000000, "maxPriorityFeePerGas": 2000000000, "from": "{ANVIL0}"}}']})

ev("transactions-22-legacy-v-chainid", "Chain id from a legacy v", "EIP-155 folds the chain id into v. Unfold it.",
"""A legacy (type 0) transaction carries v = 1811 in its signature. Which chain id was it signed for?
End your reply with a line of the form "Answer: <integer>".""", {"type": "bigint", "expect": 888}, reference="Answer: 888",
checks={"must_fail": ["Answer: 1776", "Answer: 905", "Answer: 1811"]})

ZERO_TX = "0x02dd01808080809470997970c51812dc3a010c7d01b50e0d17dc79c88080c0"
ev("transactions-23-serialize-zero-tx", "Serialize a transaction", "RLP encodes zero as an empty string. Most models write 00.",
f"""Serialize, unsigned and ready for hashing, an EIP-1559 transaction with these fields: chainId 1, nonce 0, maxPriorityFeePerGas 0, maxFeePerGas 0, gasLimit 0, to {ANVIL1}, value 0, empty data, empty access list. Give the exact typed-envelope bytes as one hex string.
End your reply with a line of the form "Answer: 0x<hex>".""", {"type": "exact", "expect": ZERO_TX}, reference="Answer: " + ZERO_TX,
checks={"must_fail": ["Answer: 0x02e1010000000000009470997970c51812dc3a010c7d01b50e0d17dc79c8000000c0", "Answer: " + ZERO_TX[2:]]})

ev("transactions-24-7702-self-nonce", "EIP-7702 authorization nonce", "The transaction increments the nonce before the tuple is checked.",
"""An EOA whose current nonce is 5 wants to delegate itself to an EIP-7702 implementation and pays for the type-4 transaction itself: the transaction sender and the authorization signer are the same account. What nonce must the authorization tuple carry for the delegation to take effect?
End your reply with a line of the form "Answer: <integer>".""", {"type": "bigint", "expect": 6}, reference="Answer: 6",
checks={"must_fail": ["Answer: 5", "Answer: 0", "Answer: 7"]})

SAFE = "0x111CEEee040739fD91D29C34C33E6B3E112F2177"; SAFE_DATA = "0x0d582f130000000000000000000000000c75fa5a5f1c0997e3eea425cfa13184ed0ec9e50000000000000000000000000000000000000000000000000000000000000003"
SAFE_HASH = "0x0cb7250b8becd7069223c54e2839feaed4cee156363fbfe5dd0a48e75c4e25b3"
ev("transactions-25-safe-tx-hash", "Safe transaction hash", "The hash the hardware wallet shows. bytes are hashed inside the struct; the domain has no name or version.",
f"""A Safe (v1.3.0+) at {SAFE} on Arbitrum One (chain id 42161) has a pending transaction:

  to            {SAFE}
  value         0
  data          {SAFE_DATA}
  operation     0
  safeTxGas     0
  baseGas       0
  gasPrice      0
  gasToken      0x0000000000000000000000000000000000000000
  refundReceiver 0x0000000000000000000000000000000000000000
  nonce         234

The Safe signs EIP-712 typed data with domain type EIP712Domain(uint256 chainId,address verifyingContract) and primary type SafeTx(address to,uint256 value,bytes data,uint8 operation,uint256 safeTxGas,uint256 baseGas,uint256 gasPrice,address gasToken,address refundReceiver,uint256 nonce).

Compute the Safe transaction hash the owners sign, the value a hardware wallet would display for verification.
End your reply with a line of the form "Answer: 0x<hex>".""", {"type": "exact", "expect": SAFE_HASH}, reference="Answer: " + SAFE_HASH,
checks={"must_pass": ["Answer: 0x" + SAFE_HASH[2:].upper()], "must_fail": ["Answer: 0xd9109ea63c50ecd3b80b6b27ed5c5a9fd3d546c2169dfb69bfa7ba24cd14c7a5", "Answer: 0x1cf7f9b1efe3bc47fe02fd27c649fea19e79d66040683a1c86c7490c80bf7291"]})

# ---- security
PERMIT_JSON = '{"types":{"EIP712Domain":[{"name":"name","type":"string"},{"name":"version","type":"string"},{"name":"chainId","type":"uint256"},{"name":"verifyingContract","type":"address"}],"Permit":[{"name":"owner","type":"address"},{"name":"spender","type":"address"},{"name":"value","type":"uint256"},{"name":"nonce","type":"uint256"},{"name":"deadline","type":"uint256"}]},"primaryType":"Permit","domain":{"name":"USD Coin","verifyingContract":"0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48","chainId":1,"version":"2"},"message":{"owner":"' + VIT + '","spender":"' + SPENDER + '","value":"1033366316628","nonce":1,"deadline":1678709555}}'
ev("security-21-malicious-permit", "A permit request", "No transaction, no gas, no activity row. Read the spender, the amount and the deadline.",
f"""A site the user has never used before pops a wallet prompt: eth_signTypedData_v4 with this payload, for the user's account {VIT} on Ethereum mainnet. Today is 2026-09-21.

{PERMIT_JSON}

What would signing this do? Is it safe? What should the user do?

Write your answer to answer.md in this directory. Be specific about the amount, the spender and the dates.""",
expect=[
 "answer.md identifies this as an EIP-2612 permit on mainnet USDC (the verifyingContract 0xa0b8…eb48, 'USD Coin' version 2) that would grant the spender 0x1661…3Ee3 an allowance of 1,033,366.316628 USDC — the value 1033366316628 read with USDC's 6 decimals; 'about 1.03 million USDC' counts. Reading it as 1033 USDC or as an 18-decimal amount fails.",
 "It explains that the signature alone grants the allowance: nothing is broadcast by the user, no gas is paid, nothing appears in the wallet's activity; the spender later submits permit() and then transferFrom to pull the tokens.",
 "It reads the deadline: 1678709555 is 2023-03-13, already past, so this exact permit would fail permit()'s deadline check today — and it still treats the request as hostile (an unknown spender, an unfamiliar site), not as harmless. An answer that says it is fine to sign because it is expired fails; an answer that never notices the deadline has passed fails.",
 "It tells the user not to sign, and to check the USDC allowance for that spender (and revoke it) if anything similar was ever signed with a live deadline.",
])

PERMIT2_JSON = '{"types":{"EIP712Domain":[{"name":"name","type":"string"},{"name":"chainId","type":"uint256"},{"name":"verifyingContract","type":"address"}],"PermitBatch":[{"name":"details","type":"PermitDetails[]"},{"name":"spender","type":"address"},{"name":"sigDeadline","type":"uint256"}],"PermitDetails":[{"name":"token","type":"address"},{"name":"amount","type":"uint160"},{"name":"expiration","type":"uint48"},{"name":"nonce","type":"uint48"}]},"primaryType":"PermitBatch","domain":{"name":"Permit2","chainId":1,"verifyingContract":"' + PERMIT2 + '"},"message":{"details":[{"token":"' + USDC + '","amount":"1461501637330902918203684832716283019655932542975","expiration":"1900000000","nonce":"0"},{"token":"' + WETH + '","amount":"1461501637330902918203684832716283019655932542975","expiration":"1900000000","nonce":"0"},{"token":"' + DAI + '","amount":"1461501637330902918203684832716283019655932542975","expiration":"1900000000","nonce":"0"}],"spender":"' + SPENDER + '","sigDeadline":"1900000000"}}'
ev("security-22-permit2-batch", "A Permit2 batch", "One signature, three tokens, unlimited, for years. Explain the two layers.",
f"""A wallet prompt from a site the user just connected to: eth_signTypedData_v4 with this payload, for the user's account {VIT} on Ethereum mainnet. The user has previously approved USDC, WETH and DAI to the Permit2 contract while using Uniswap. Today is 2026-09-21.

{PERMIT2_JSON}

What does signing this authorize, exactly? What should the user do?

Write your answer to answer.md in this directory. Be specific about the amounts, the spender and the dates.""",
expect=[
 "answer.md identifies this as a Permit2 PermitBatch (the canonical Permit2 contract at 0x0000…BA3): one signature sets three allowances at once, USDC, WETH and DAI, for the spender 0x1661…3Ee3.",
 "It reads the amount 1461501637330902918203684832716283019655932542975 as the maximum uint160, i.e. unlimited, and the expiration 1900000000 as March 2030, so the spender can pull any amount of all three tokens for years. It distinguishes sigDeadline (how long the signature can be submitted) from expiration (how long the allowance lasts).",
 "It explains the two layers: because the user already approved these tokens to Permit2, this signature is all the spender needs — the spender submits it to Permit2 and then calls Permit2's transferFrom, with no further action or transaction from the user. Revoking means revoking the spender inside Permit2 (approve 0 / lockdown) or revoking the token approvals to Permit2 itself.",
 "It treats an unknown spender receiving unlimited batch allowances from a just-connected site as a drain pattern and tells the user not to sign.",
])

ev("security-23-decimal-verifying-contract", "A decimal is still an address", "Normalize before you match against a list.",
"""A dapp sends eth_signTypedData_v4 whose domain contains "verifyingContract": 917551056842671309452305380979543736893630245704 — a JSON number, not a hex string. Wallet security checks compare the domain against a list of known token contracts. Which contract's domain is this?
End your reply with a line of the form "Answer: <checksummed 0x address>".""", {"type": "exact", "expect": USDC}, reference="Answer: " + USDC,
checks={"must_pass": ["Answer: " + USDC.lower()], "must_fail": ["Answer: 917551056842671309452305380979543736893630245704"]})

ev("security-24-siwe-domain", "Sign-in domain binding", "The message names one site; the request comes from another.",
f"""A wallet receives a personal_sign request from the origin https://opensea-rewards.xyz. The message is:

opensea.io wants you to sign in with your Ethereum account:
{VIT}

URI: https://opensea.io
Version: 1
Chain ID: 1
Nonce: 8f3c1a9b
Issued At: 2026-09-21T10:00:00Z

What should the wallet do?
A) Sign: the message names opensea.io, which is a legitimate site
B) Refuse or warn loudly: in Sign-In with Ethereum the domain in the message must be the origin making the request; a mismatch means the requesting site is collecting a signature that logs the user in to opensea.io from somewhere else
C) Sign: personal_sign cannot move funds, so there is nothing to protect
D) Sign after checking the nonce has not been used before
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("security-25-safe-delegatecall", "Operation 1", "The decoded inner calls tell you nothing if the target runs as the Safe.",
f"""A Safe multisig transaction is waiting for your signature. The other owners have signed. Fields: to = 0x40A2aCCbd92BCA938b02010E17A5b8929b49130D (a MultiSend contract), value = 0, operation = 1, data = multiSend(...) whose decoded contents are a routine ERC-20 transfer to a known address. What does operation = 1 mean, and why is it the first field to check?
A) 1 means "batch": it only tells the Safe that several calls are packed in the data
B) 1 means DELEGATECALL: the target's code runs with the Safe's own storage and address, so a malicious target can rewrite the Safe's storage — including the singleton (mastercopy) slot — and take the Safe over, regardless of what the decoded inner calls look like; this is how the Bybit Safe was drained
C) 1 means CALL with value; it only matters when ETH is attached
D) operation is informational; the Safe ignores it when executing
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

# ---- building
ev("building-21-5792-fallback", "Batching that cannot batch", "A wallet without wallet_sendCalls must not silently split an atomic batch.",
f"""Your dapp sends a batch through EIP-5792 wallet_sendCalls with the atomic capability required (approve then swap, all or nothing) and a paymasterService capability so the user pays no gas. The connected wallet returns "method not found" for wallet_sendCalls. What should your client library do?
A) Fall back to one eth_sendTransaction per call so the flow still works
B) Throw: the caller required atomic execution and a capability the wallet cannot honor; falling back would run the calls non-atomically (approve can land without the swap) and silently drop the sponsorship
C) Retry wallet_sendCalls with the older parameter shape
D) Send only the first call and let the user retry the rest
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("building-22-sign-transaction", "eth_signTransaction", "Signing is not sending.",
f"""You are implementing eth_signTransaction in a wallet. Which behaviour is correct?
A) Sign the transaction, broadcast it, and return the transaction hash
B) Sign the transaction and return the raw signed transaction bytes; do not broadcast — the caller decides if and when to submit it with eth_sendRawTransaction
C) Return only the signature components r, s and v
D) Behave like eth_sendTransaction but skip the confirmation prompt, since the dapp is only asking for a signature
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

SIG65 = "0x7c39e44a296c8b49b33ca5d4f1c2b6ca6472f9ee98a864d3d7601e20ffc370c613fd866a0df8427cb1db9fca2e68bdfe195ff3f0405b451aa9054f5b7c6ceb331c"
SIG64 = "0x7c39e44a296c8b49b33ca5d4f1c2b6ca6472f9ee98a864d3d7601e20ffc370c693fd866a0df8427cb1db9fca2e68bdfe195ff3f0405b451aa9054f5b7c6ceb33"
ev("building-23-compact-signature", "ERC-2098 compact signature", "Fold v into the top bit of s. Dropping v is not the same thing.",
f"""A signer produced this 65-byte ECDSA signature, r || s || v:

{SIG65}

Convert it to the 64-byte ERC-2098 compact form.
End your reply with a line of the form "Answer: 0x<hex>".""", {"type": "exact", "expect": SIG64}, reference="Answer: " + SIG64,
checks={"must_fail": ["Answer: " + SIG65[:-2], "Answer: " + SIG65]})

ev("building-24-4337-2d-nonce", "Two-dimensional nonces", "Key in the high 192 bits, sequence in the low 64.",
"""ERC-4337 EntryPoint nonces are two-dimensional: a 192-bit key and a 64-bit sequence. An account has executed exactly one UserOperation on key 1 and nothing else. What does EntryPoint.getNonce(account, 1) return?
End your reply with a line of the form "Answer: <integer, plain decimal>".""", {"type": "bigint", "expect": (1 << 64) + 1}, reference="Answer: 18446744073709551617",
checks={"must_fail": ["Answer: 1", "Answer: 2", "Answer: 18446744073709551616"]})

HM = "0xefedd0a9a0294228c3977d7fbb68c7d40279f8b408cf3e24ef1823b179709e58"
ev("building-25-hash-message-string", "personal_sign of a hex-looking string", "The characters, not the bytes. The prefix length follows.",
"""A dapp calls personal_sign with the message given as the ten-character text string 0xdeadbeef — the characters, not four bytes. What 32-byte digest does the wallet actually sign?
End your reply with a line of the form "Answer: 0x<hex>".""", {"type": "exact", "expect": HM}, reference="Answer: " + HM,
checks={"must_fail": ["Answer: 0xd1c7f1a06a4f9a535077e50ad23244ce2c6ae443fcd412965226f3df5d28eaaa"]})

# ---- concepts
ev("concepts-21-7702-chainid-zero", "Authorization for every chain", "chainId 0 is not 'unset'.",
f"""An EIP-7702 authorization tuple a dapp asks the wallet to sign has chainId = 0. What does that mean, and how should a wallet treat it?
A) It is invalid; a chain id must be 1 or higher, so the wallet can just reject it
B) It is valid on every chain: the same signed tuple can be included on any EVM chain to delegate the account there, so the wallet should refuse or warn loudly unless the delegate contract is known-good everywhere
C) It means Ethereum mainnet by convention
D) It binds the authorization to whichever chain first includes it
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

ev("concepts-22-7702-no-recursion", "Delegation does not chain", "One hop. The second designator is not code.",
f"""Under EIP-7702, account A is delegated to B (A's code is 0xef0100 followed by B's address), and B is itself an EOA delegated to C. A transaction calls A. What runs?
A) C's code: delegation resolves transitively until real bytecode is found
B) Only one hop is followed: the EVM loads B's code, which is B's own 23-byte delegation designator, not C's code; the designator is not executable, so the call fails without running anything useful
C) The transaction is invalid and never enters a block
D) B's code, but with C's storage
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("concepts-23-7702-bad-tuple", "A bad tuple is not a bad transaction", "Invalid authorizations are skipped; an empty list is invalid.",
f"""A type-4 transaction carries two authorization tuples. One was signed for a different chain id. What happens when the transaction is included?
A) The whole transaction is invalid and cannot be included
B) The mismatched tuple is skipped, the other is applied, the transaction executes normally and is charged for both tuples; only an empty authorization list makes the transaction itself invalid
C) The transaction reverts and the sender pays nothing
D) Both tuples are applied, because authorizations are validated at signing time, not at inclusion
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: D"]})

ev("concepts-24-4337-banned-opcodes", "Why validation bans TIMESTAMP", "Simulation has to predict inclusion.",
f"""ERC-4337 bundlers reject a UserOperation whose validateUserOp reads TIMESTAMP, NUMBER, BLOCKHASH or BALANCE (unstaked). Why?
A) Those opcodes are too expensive inside validation
B) The bundler simulates validation before inclusion and eats the gas if it fails on-chain; opcodes whose result changes between simulation and inclusion let a UserOperation pass simulation and then fail, a griefing vector — time bounds are expressed instead through validUntil and validAfter in the validation return value
C) The EVM forbids environment opcodes in static calls, and validation runs as a static call
D) They would reveal the bundler's identity to the account
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

ev("concepts-25-1271-replay-safe", "One owner, many accounts", "Why a smart account wraps the hash before the owner signs it.",
f"""A smart account owned by the EOA K does not let K sign an ERC-1271 hash directly. It wraps it first: K signs hashTypedData(domain{{chainId, verifyingContract: this account}}, Message(bytes32 hash)). Why?
A) It saves gas in isValidSignature
B) K may own other accounts on this and other chains; a bare signature by K over the hash would satisfy isValidSignature on every account K owns, so a signature produced for one account could be replayed as another account's approval (a permit, an order). Binding the account's own domain into the digest makes it valid for one account on one chain.
C) ERC-1271 requires the signed data to be EIP-712 typed data
D) It hides the original message from the verifier
{ANS}""", mc("B"), reference="Answer: B", checks={"must_fail": ["Answer: A", "Answer: C"]})

for d in E:
    p = os.path.join(OUT, d["pillar"], d["id"] + ".yaml")
    with open(p, "w") as fh: yaml.dump(d, fh, sort_keys=False, allow_unicode=True, width=110)
print(f"wrote {len(E)} authored evals")
