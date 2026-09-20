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

for d in E:
    p = os.path.join(OUT, d["pillar"], d["id"] + ".yaml")
    with open(p, "w") as fh: yaml.dump(d, fh, sort_keys=False, allow_unicode=True, width=110)
print(f"wrote {len(E)} authored evals")
