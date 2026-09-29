#!/usr/bin/env python3
"""Write the rpc evals. Expected values are never typed by hand: they are read from the
ethereum/execution-apis conformance fixtures (tests/<method>/*.io, Hive-enforced, never speconly)
or computed from the EIP formulas. See docs/research/rpc-evals.md. Clone execution-apis next
to this repo, or pass --src. Re-run after editing; it overwrites its own files only."""
import argparse, json, os, re, yaml
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "evals")
ap_ = argparse.ArgumentParser(); ap_.add_argument("--src", default=os.path.join(ROOT, "..", "execution-apis"))
SRC = ap_.parse_args().src

def fx(path):
    req = res = None
    for l in open(os.path.join(SRC, "tests", path)):
        if l.startswith(">> "): req = json.loads(l[3:])
        elif l.startswith("<< "): res = json.loads(l[3:])
    return req, res

class Lit(str): pass
yaml.add_representer(Lit, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))
def mc(letter): return {"type": "any_of", "options": [{"type": "exact", "expect": letter}, {"type": "regex", "pattern": rf"^\(?{letter}\b"}]}
ANS = 'End your reply with a line of the form "Answer: <letter>".'
MD = "Write your answer to answer.md in this directory."
SPEC = "ethereum/execution-apis"
E = []
def ev(id, title, summary, prompt, grader=None, expect=None, reference=None, checks=None, source=None):
    d = {"id": id, "pillar": id.split("-")[0], "title": title, "kind": "quiz", "summary": summary, "prompt": Lit(prompt.strip() + "\n")}
    if grader: d["grader"] = grader
    if expect: d["expect"] = expect
    if reference: d["reference"] = reference
    if checks: d["checks"] = checks
    d["source"] = {"repo": SPEC, "task": source} if source else {"repo": "austintgriffith/ethevals", "task": id}
    E.append(d)
def js(o): return json.dumps(o)

# ---------------- deterministic: fixture values and EIP formulas
batch = [{"jsonrpc": "2.0", "method": "eth_blockNumber", "id": 1}, {"jsonrpc": "2.0", "method": "eth_chainId"}, {"jsonrpc": "2.0", "method": "eth_fooBar"},
         {"jsonrpc": "2.0", "method": "eth_blockNumber", "id": None}, {"foo": "boo"}, 1, {"jsonrpc": "2.0", "method": "eth_fooBar", "id": "7"}]
bres = {"responses": 5, "results": 2, "invalid_request": 2, "method_not_found": 1, "empty_batch": "object", "all_notifications_batch": "nothing"}
ev("rpc-01-batch-edge-cases", "A batch, exactly", "A notification is a request without an id member. id: null is not a notification.",
f"""A server implements JSON-RPC 2.0 exactly. It knows eth_blockNumber and eth_chainId, and no method named eth_fooBar. It receives this batch in one HTTP request:

  {js(batch)}

How many response objects does it send back, how many of them carry a `result`, and how many carry each error code? Then: what does it send back for the batch `[]`, and for a batch that contains only notifications? Use "array", "object" or "nothing" for those two.
Reply with JSON only: {{"responses": <int>, "results": <int>, "invalid_request": <count of -32600>, "method_not_found": <count of -32601>, "empty_batch": "array|object|nothing", "all_notifications_batch": "array|object|nothing"}}""",
{"type": "json", "expect": bres}, reference=js(bres),
checks={"must_fail": [js(dict(bres, responses=4, results=1)), js(dict(bres, method_not_found=2, responses=6)), js(dict(bres, empty_batch="array")), js(dict(bres, all_notifications_batch="array")), js(dict(bres, invalid_request=1, responses=4))]})

def sim(path):
    req, res = fx("eth_simulateV1/ethSimulate-" + path + ".io"); return req["params"][0], res
base = sim("empty-with-block-num-set-current")[1]["result"][0]
HEAD, HEAD_TS = int(base["number"], 16) - 1, int(base["timestamp"], 16) - 12
ts_req, ts_res = sim("block-timestamp-auto-increment")
assert ts_res["error"]["code"] == -38021
tso = {"error": ts_res["error"]["code"]}
ev("rpc-02-simulate-timestamps", "Simulated timestamps", "An unset simulated timestamp is parent + 12, and timestamps must strictly increase.",
f"""The node's head is block {hex(HEAD)} with timestamp {hex(HEAD_TS)}. A wallet sends eth_simulateV1 at "latest" with:

  {js(ts_req)}

What does a node that passes the execution-apis conformance fixtures (the Hive rpc-compat suite) return? If the request succeeds, list the timestamp of every simulated block; if it fails, give the JSON-RPC error code.
Reply with JSON only: {{"timestamps": ["0x...", ...]}} or {{"error": <integer code>}}""",
{"type": "json", "expect": tso}, reference=js(tso),
checks={"must_fail": [js({"timestamps": ["0x227", "0x228", "0x228", "0x229"]}), js({"timestamps": ["0x227", "0x233", "0x228", "0x234"]}), js({"error": -38020})]},
source="tests/eth_simulateV1/ethSimulate-block-timestamp-auto-increment.io")

gp_req, gp_res = sim("blocknumber-increment")
blocks = gp_res["result"]
gap = {"blocks": len(blocks), "last_number": int(blocks[-1]["number"], 16), "last_timestamp": int(blocks[-1]["timestamp"], 16),
       "timestamp_of_0x3f": int(next(b for b in blocks if b["number"] == "0x3f")["timestamp"], 16), "timestamp_of_0x41": int(next(b for b in blocks if b["number"] == "0x41")["timestamp"], 16)}
ev("rpc-03-simulate-gap-blocks", "Simulated block numbers", "A jump in block number is filled with empty blocks. Every later block is parent + 1 and parent + 12 s.",
f"""The node's head is block {hex(HEAD)} with timestamp {hex(HEAD_TS)}. A client sends eth_simulateV1 at "latest" with:

  {js(gp_req)}

On a node that passes the execution-apis conformance fixtures (the Hive rpc-compat suite), the request succeeds. How many blocks does the result array contain, what are the number and timestamp of the last one, and what are the timestamps of blocks 0x3f and 0x41?
Reply with JSON only (integers or 0x-hex): {{"blocks": ..., "last_number": ..., "last_timestamp": ..., "timestamp_of_0x3f": ..., "timestamp_of_0x41": ...}}""",
{"type": "json", "expect": gap}, reference=js(gap),
checks={"must_fail": [js(dict(gap, blocks=10, last_number=0x57)), js(dict(gap, blocks=10, last_number=0x57, last_timestamp=0x224 + 12 * 10)), js(dict(gap, timestamp_of_0x41=0x411))]},
source="tests/eth_simulateV1/ethSimulate-blocknumber-increment.io")

T = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"; APPROVAL = "0x8c5be1e5ebec7d5bd14f71427b1e84f3dd0314c0f7b2291e5b200ac8c7c3b925"
def pad(a): return "0x" + "0" * 24 + a[2:].lower()
A = pad("0x1111111111111111111111111111111111111111"); B = pad("0x2222222222222222222222222222222222222222"); C = pad("0x3333333333333333333333333333333333333333")
logs = {"L1": [T, A, C], "L2": [T, C, A], "L3": [APPROVAL, B, A], "L4": [T], "L5": [T, C, B]}
flt = [None, [A, B]]
match = [k for k, t in logs.items() if all(f is None or (i < len(t) and (t[i] in f if isinstance(f, list) else t[i] == f)) for i, f in enumerate(flt))]
assert match == ["L1", "L3"]
ev("rpc-04-topic-filter", "eth_getLogs topic filters", "Topics match by position. null is a wildcard; an inner array is OR.",
f"""Let
  A = {A}
  B = {B}
  C = {C}
  TRANSFER = {T}
  APPROVAL = {APPROVAL}

Five logs from the same contract have these topics:
  L1: [TRANSFER, A, C]
  L2: [TRANSFER, C, A]
  L3: [APPROVAL, B, A]
  L4: [TRANSFER]
  L5: [TRANSFER, C, B]

An eth_getLogs request covers their blocks with "topics": [null, [A, B]]. Which logs does a spec-conformant node return?
Reply with JSON only: a list of the matching labels in the order listed above.""",
{"type": "json", "expect": match}, reference=js(match),
checks={"must_fail": [js(["L1", "L2", "L3", "L5"]), js(["L1", "L3", "L4"]), js(["L1"]), js(["L1", "L2", "L3"])]},
source="tests/eth_getLogs/topic-null-wildcard.io")

mv_req, mv_res = sim("move-ecrecover-and-call")
b2c, b2r = mv_req["blockStateCalls"][1]["calls"], mv_res["result"][1]["calls"]
NEW = next(iter(mv_req["blockStateCalls"][1]["stateOverrides"].values()))["movePrecompileToAddress"]
assert b2c[1]["to"] == NEW and b2c[2]["to"] == "0x0000000000000000000000000000000000000001" and b2c[2]["input"] == b2c[1]["input"]
recovered = mv_res["result"][0]["calls"][1]["returnData"]
mvo = {"call_new_address": {"status": int(b2r[1]["status"], 16), "returnData": b2r[1]["returnData"]}, "call_0x01": {"status": int(b2r[2]["status"], 16), "returnData": b2r[2]["returnData"]}}
ev("rpc-05-move-precompile", "Moving a precompile", "movePrecompileToAddress moves ecrecover. The old address is left empty: a call to it succeeds and returns nothing.",
f"""A client sends eth_simulateV1 at "latest" with two blocks. In block 1, a call to ecrecover at 0x0000000000000000000000000000000000000001 with this input returns {recovered}:

  {b2c[1]["input"]}

Block 2 applies the state override {{"0x0000000000000000000000000000000000000001": {{"movePrecompileToAddress": "{NEW}"}}}}, then sends that same input twice: first to {NEW}, then to 0x0000000000000000000000000000000000000001. No other overrides apply.
What status and returnData does each of the two block-2 calls get?
Reply with JSON only: {{"call_new_address": {{"status": <0 or 1>, "returnData": "0x..."}}, "call_0x01": {{"status": <0 or 1>, "returnData": "0x..."}}}}""",
{"type": "json", "expect": mvo}, reference=js(mvo),
checks={"must_fail": [js({"call_new_address": mvo["call_new_address"], "call_0x01": {"status": 1, "returnData": recovered}}), js({"call_new_address": mvo["call_new_address"], "call_0x01": {"status": 0, "returnData": "0x"}}), js({"call_new_address": {"status": 1, "returnData": "0x"}, "call_0x01": mvo["call_new_address"]})]},
source="tests/eth_simulateV1/ethSimulate-move-ecrecover-and-call.io")

nb = fx("eth_getBlockByNumber/get-block-notfound.io")[1]; nr = fx("eth_getBlockReceipts/get-block-receipts-future.io")[1]; nl = fx("eth_getLogs/filter-error-future-block-range.io")[1]
assert nb["result"] is None and nr["result"] is None and "error" in nl
ev("rpc-06-beyond-head", "Past the head", "A block past the head is null. A log range past the head is an error, never clamped.",
f"""A node's head is block 0x36. A client sends three requests:

  eth_getBlockByNumber("0x40", false)
  eth_getBlockReceipts("0x40")
  eth_getLogs({{"fromBlock": "0x30", "toBlock": "0x40"}})

What does a spec-conformant node return?
A) An error for all three: block 0x40 does not exist yet
B) `result: null` for all three
C) `result: null` for the two block methods; an invalid-params error ({nl["error"]["code"]}) for eth_getLogs, because its range extends beyond the head
D) `result: null` for the two block methods; for eth_getLogs, the logs from 0x30 to 0x36, with the range clamped to the head
{ANS}""", mc("C"), reference="Answer: C", checks={"must_fail": ["Answer: D", "Answer: B"]},
source="src/eth/filter.yaml")

BF = 100
txs = [("0x2", 150, 30, 21000), ("0x0", 180, None, 50000), ("0x2", 105, 20, 100000), ("0x2", 300, 2, 29000), ("0x2", 200, 60, 300000)]
def tip(t, fee, pri): return fee - BF if pri is None else min(pri, fee - BF)
PCT = [10, 25, 50, 88, 99]
srt = sorted(((tip(t, f, p), g) for t, f, p, g in txs), key=lambda x: x[0]); used = sum(g for *_, g in txs)
def reward(p):
    i, s = 0, srt[0][1]
    while s < int(used * p / 100) and i < len(srt) - 1: i += 1; s += srt[i][1]
    return srt[i][0]
assert all(int(used * p / 100) not in [sum(g for _, g in srt[:k + 1]) for k in range(len(srt))] for p in PCT)
rw = [reward(p) for p in PCT]
rows = "\n".join(f"  tx{i}: type {t}, " + (f"gasPrice {f}" if p is None else f"maxFeePerGas {f}, maxPriorityFeePerGas {p}") + f", receipt gasUsed {g}" for i, (t, f, p, g) in enumerate(txs))
ev("rpc-07-fee-history-rewards", "eth_feeHistory reward percentiles", "Percentiles are weighted by gas used, over effective tips, not by transaction count over tip fields.",
f"""A block has baseFeePerGas {BF} wei and gasUsed {used}. It contains exactly these transactions (fees in wei):

{rows}

A client calls eth_feeHistory for this one block with rewardPercentiles {PCT}. What reward values does the node return for this block, in wei?
Reply with JSON only: a list of {len(PCT)} integers, one per percentile, in order.""",
{"type": "json", "expect": rw}, reference=js(rw),
checks={"must_fail": [js([2, 5, 30, 60, 80]), js([2, 20, 60, 60, 80]), js([5, 5, 60, 80, 80]), js([2, 2, 30, 80, 80])]},
source="src/eth/fee_market.yaml")

def fexp(f, n, d):
    i, o, a = 1, 0, f * d
    while a > 0: o += a; a = a * n // (d * i); i += 1
    return o // d
cfg = fx("eth_config/get-config.io")[1]["result"]["current"]["blobSchedule"]
TGT, MAX, FRAC, GPB, BBC = cfg["target"], cfg["max"], cfg["baseFeeUpdateFraction"], 1 << 17, 1 << 13
P_EX, P_USED, P_BF = GPB * 1500, 0, 10 ** 9
def next_excess(ex, used_, bf):
    if ex + used_ < TGT * GPB: return 0
    if BBC * bf > GPB * fexp(1, ex, FRAC): return ex + used_ * (MAX - TGT) // MAX
    return ex + used_ - TGT * GPB
nx = next_excess(P_EX, P_USED, P_BF); old = P_EX + P_USED - TGT * GPB
assert nx != old and fexp(1, nx, FRAC) != fexp(1, old, FRAC)
blob = {"excessBlobGas": nx, "blobBaseFee": fexp(1, nx, FRAC)}
ev("rpc-08-next-blob-fee", "The next block's blob fee", "Post-Osaka, EIP-7918: when blobs are priced below the reserve, excess blob gas does not fall.",
f"""A post-Osaka node (EIP-7918 active) returns this from eth_config (current fork): "blobSchedule": {js(cfg)}. Its head block N has excessBlobGas {P_EX}, blobGasUsed {P_USED}, and baseFeePerGas {P_BF} wei. Block N+1 is in the same fork.
What excessBlobGas will block N+1 have, and what blob base fee per blob gas (in wei) do blob transactions pay in block N+1?
Reply with JSON only: {{"excessBlobGas": <int>, "blobBaseFee": <int>}}""",
{"type": "json", "expect": blob}, reference=js(blob),
checks={"must_fail": [js({"excessBlobGas": old, "blobBaseFee": fexp(1, old, FRAC)}), js({"excessBlobGas": nx, "blobBaseFee": fexp(1, nx, 5007716)}), js({"excessBlobGas": 0, "blobBaseFee": 1})]},
source="tests/eth_config/get-config.io")

GL = 36_000_000
def next_bf(bf, gu, gl):
    tgt = gl // 2
    if gu == tgt: return bf
    if gu > tgt: return bf + max(1, bf * (gu - tgt) // tgt // 8)
    return max(0, bf - bf * (tgt - gu) // tgt // 8)
BF0, GUS = 7, [GL // 2 + 1, 3_141_592, GL]
arr = [BF0]
for gu in GUS: arr.append(next_bf(arr[-1], gu, GL))
assert arr == [7, 8, 8, 9]
ev("rpc-09-next-base-fee", "Integer base fees", "EIP-1559 is integer arithmetic: an increase is at least 1 wei, and a small decrease can round to 0.",
f"""Three consecutive post-London blocks N-2, N-1 and N each have gasLimit {GL}. Block N-2 has baseFeePerGas {BF0} wei. Their gasUsed values are {GUS[0]}, {GUS[1]} and {GUS[2]}, in that order.
A client calls eth_feeHistory with blockCount 3 and newestBlock N. What is the baseFeePerGas array in the result, in wei?
Reply with JSON only: a list of integers.""",
{"type": "json", "expect": arr}, reference=js(arr),
checks={"must_fail": [js([7, 7, 7, 8]), js([7, 8, 8]), js([7, 8, 7, 8]), js([7, 7, 6, 7])]},
source="src/eth/fee_market.yaml")

og_req, og_res = sim("run-out-of-gas-in-block-38015")
b2 = og_res["result"][1]; c1, c2 = b2["calls"]
assert not og_req["blockStateCalls"][0].get("calls")
ogo = {"block2_gasLimit": int(b2["gasLimit"], 16), "call1_status": int(c1["status"], 16), "call2_status": int(c2["status"], 16), "call2_gasUsed": int(c2["gasUsed"], 16), "call2_error_code": c2["error"]["code"]}
ev("rpc-10-simulate-block-gas", "Gas in a simulated block", "A gasLimit override carries to the next simulated block, and a call without gas gets only what is left in the block.",
f"""The chain's blocks have gasLimit 200000000. A client sends eth_simulateV1 at "latest" to a node that passes the execution-apis conformance fixtures (the Hive rpc-compat suite), with two blocks and "validation" omitted.
- Block 1 has blockOverrides {{"gasLimit": "{og_req["blockStateCalls"][0]["blockOverrides"]["gasLimit"]}"}} and no calls.
- Block 2 has no overrides. It makes two identical calls from a funded account to a contract, with no `gas` field. The contract's function loops, burning gas, until it has used 1,000,000 gas since it started, then returns. If it runs out of gas first, the call fails.
The first call in block 2 succeeds, and its gasUsed is {int(c1["gasUsed"], 16)}. What gasLimit does block 2 report, and what status, gasUsed and error code does the second call get?
Reply with JSON only (integers or 0x-hex): {{"block2_gasLimit": ..., "call1_status": ..., "call2_status": ..., "call2_gasUsed": ..., "call2_error_code": <integer, or null if none>}}""",
{"type": "json", "expect": ogo}, reference=js(ogo),
checks={"must_fail": [js(dict(ogo, block2_gasLimit=200000000, call2_status=1, call2_gasUsed=int(c1["gasUsed"], 16), call2_error_code=None)), js(dict(ogo, call2_error_code=-38015)), js(dict(ogo, block2_gasLimit=200000000))]},
source="tests/eth_simulateV1/ethSimulate-run-out-of-gas-in-block-38015.io")

gc_req, gc_res = fx("eth_getCode/get-code-eip7702-delegation.io")
eoa, code = gc_req["params"][0], gc_res["result"]; assert code.startswith("0xef0100") and len(code) == 48
ev("rpc-11-7702-get-code", "eth_getCode of a delegated EOA", "A 7702 EOA has code: the 23-byte delegation designator, not the delegate's bytecode.",
f"""The EOA {eoa} set an EIP-7702 delegation to the contract 0x{code[8:]}. What does eth_getCode("{eoa}", "latest") return?
Answer with only the full 0x-prefixed hex string on the last line, as: Answer: 0x...""",
{"type": "any_of", "options": [{"type": "exact", "expect": code}, {"type": "regex", "pattern": rf"^`?{code}\b"}]}, reference="Answer: " + code,
checks={"must_pass": [f"Answer: {code} (0xef0100 followed by the delegate address)"], "must_fail": ["Answer: 0x", "Answer: 0x" + code[8:], "Answer: 0xef0000" + code[8:]]},
source="tests/eth_getCode/get-code-eip7702-delegation.io")

DB, DC, DD, DE = ("0x" + c * 40 for c in "bcde")
tuples = [(1, DB, 0), (5, DC, 1), (0, DD, 1), (1, DE, 1), (1, "0x" + "0" * 40, 2)]
nonce, dcode = 0, "0x"
for cid_, addr_, n_ in tuples:
    if cid_ not in (0, 1) or n_ != nonce: continue
    nonce += 1; dcode = "0x" if int(addr_, 16) == 0 else "0xef0100" + addr_[2:]
t7 = {"nonce": nonce, "code": dcode}
assert t7 == {"nonce": 3, "code": "0x"}
tl = "\n".join(f"  {i + 1}. chainId {c}, address {a}, nonce {n}" for i, (c, a, n) in enumerate(tuples))
ev("rpc-12-7702-tuples", "Five authorization tuples", "Tuples apply in order against the running nonce. chainId 0 is any chain; address 0 clears the delegation.",
f"""On Ethereum mainnet (chain ID 1), EOA X has nonce 0 and no code. A sponsor, not X, sends one type-4 transaction whose authorization list holds five tuples, all validly signed by X, in this order:

{tl}

The transaction is included. What do eth_getTransactionCount(X, "latest") and eth_getCode(X, "latest") return afterwards?
Reply with JSON only: {{"nonce": <integer>, "code": "0x..."}}""",
{"type": "json", "expect": t7}, reference=js(t7),
checks={"must_fail": [js({"nonce": 2, "code": "0xef0100" + DD[2:]}), js({"nonce": 5, "code": "0x"}), js({"nonce": 1, "code": "0xef0100" + DB[2:]}), js({"nonce": 3, "code": "0xef0100" + "0" * 40})]},
source=None)

st_req, st_res = fx("eth_simulateV1/ethSimulate-eth-send-should-produce-logs.io")
call = st_req["params"][0]["blockStateCalls"][0]["calls"][0]; lg = st_res["result"][0]["calls"][0]["logs"][0]
tlog = {"address": lg["address"], "topics": lg["topics"], "data": lg["data"]}
ev("rpc-13-simulate-transfer-logs", "ETH transfers as logs", "eth_simulateV1 with traceTransfers reports ETH moves as ERC-20 Transfer logs from 0xeeee…eeee.",
f"""A wallet previews a plain ETH transfer with eth_simulateV1 and sets "traceTransfers": true:

  {js(st_req["params"][0])}

The call succeeds and its `logs` array has exactly one entry. Give its address, topics and data.
Reply with JSON only: {{"address": "0x...", "topics": ["0x...", ...], "data": "0x..."}}""",
{"type": "json", "expect": tlog}, reference=js(tlog),
checks={"must_fail": [js(dict(tlog, address="0x0000000000000000000000000000000000000000")), js(dict(tlog, address=call["from"])), js(dict(tlog, topics=tlog["topics"][:1]))]},
source="tests/eth_simulateV1/ethSimulate-eth-send-should-produce-logs.io")

def outcome(path):
    r = sim(path)[1]
    return r["error"]["code"] if "error" in r else ("ok" if all(c["status"] == "0x1" for b in r["result"] for c in b["calls"]) else "reverted")
cases = {"a": "transaction-too-high-nonce", "b": "basefee-too-low-without-validation-38012", "c": "simple-no-funds", "d": "instrict-gas-38013", "f": "overflow-nonce"}
nv = {k: outcome(v) for k, v in cases.items()}
nv["e"] = int(sim("eth-send-should-not-produce-logs-by-default")[1]["result"][0]["baseFeePerGas"], 16)
assert nv == {"a": "ok", "b": "ok", "c": -38014, "d": -38013, "f": "ok", "e": 0}
ev("rpc-14-simulate-no-validation", "What validation off still checks", "Without validation, eth_simulateV1 skips nonce and fee checks, and the base fee is 0. It still checks balance and intrinsic gas.",
f"""Each item below is a separate eth_simulateV1 request, sent to a node that passes the execution-apis conformance fixtures (the Hive rpc-compat suite), at "latest" with one block, "validation" omitted, and no block overrides unless stated. Accounts have no code.
  a) A call from an account whose nonce is 0, with "nonce": "0x64".
  b) blockOverrides {{"baseFeePerGas": "0xa"}}; the call sets maxFeePerGas and maxPriorityFeePerGas to 0.
  c) A call that sends 1000 wei from an account with balance 0.
  d) A call with "gas": "0x0".
  e) Not a pass/fail case: a plain call with no fee fields. What baseFeePerGas does the simulated block report?
  f) A state override sets an account's nonce to 0xffffffffffffffff; two calls are then sent from it in the same block.
For a to d and f, answer "ok" if every call executes with status 0x1, or the JSON-RPC error code if the request fails. For e, give the integer.
Reply with JSON only: {{"a": ..., "b": ..., "c": ..., "d": ..., "e": ..., "f": ...}}""",
{"type": "json", "expect": nv}, reference=js(nv),
checks={"must_fail": [js(dict(nv, c="ok")), js(dict(nv, a=-38011)), js(dict(nv, f=-32603)), js(dict(nv, e=7)), js(dict(nv, d="ok"))]},
source="tests/eth_simulateV1/ethSimulate-transaction-too-high-nonce.io")

# ---------------- judged
ev("rpc-15-block-tags-for-credit", "Which block tag credits a deposit", "latest can reorg under normal conditions. finalized cannot, and it moves in jumps.",
f"""An exchange backend credits ETH deposits on Ethereum mainnet. It polls eth_getBlockByNumber("latest", true) every 12 seconds and credits every deposit it sees in that block. Support tickets report deposits that were credited and then vanished from the chain.

Which block tag should the crediting logic use? Explain what latest, safe and finalized mean on post-merge Ethereum and the tradeoff between them. Then say what else must change in the polling loop when it moves off latest. {MD}""",
expect=[
 "answer.md explains that a block returned for 'latest' can be reorged out of the canonical chain under normal conditions, so deposits credited from it can disappear.",
 "It distinguishes safe (safe from reorgs under honest-majority and synchrony assumptions) from finalized (cannot be reverted without a large share of stake being slashed or manual community intervention), and says finalized lags the head by roughly two epochs, about 13 minutes (anything in the 12-20 minute range counts).",
 "It recommends crediting at finalized (or at safe with an explicit, stated risk limit), while the UI may show the deposit as pending before that.",
 "It notes that the finalized (or safe) head advances many blocks at a time, so the loop must keep a cursor and process every block between the last processed block and the new head, instead of reading only the tagged block. An answer that polls only the single block the tag returns fails this condition.",
], source="src/schemas/block.yaml")

ev("rpc-16-removed-logs", "removed: true", "A removed log is a reorged-out event. It must be undone, not applied.",
f"""Our indexer subscribes with eth_subscribe("logs", {{"address": TOKEN}}) and, for every Transfer log it receives, moves the amount between holders in a balances table. Sometimes a log arrives with "removed": true, and the code handles it like any other Transfer.

What does "removed": true mean, what must the indexer do with such a log, and how do we make the indexer correct across reorgs? {MD}""",
expect=[
 "answer.md explains that removed: true means the log belonged to a block that was reorged out of the canonical chain, so the event no longer happened on the canonical chain (the same transaction may reappear in another block, with a new block hash).",
 "It says the indexer must reverse the effect of that log (undo the balance move). An answer that skips the removed log, or applies it again as a new Transfer, fails.",
 "It gives a structural fix for reorgs, any one of: store applied logs keyed by block hash so a reorg can be rolled back; track block hashes and rewind and replay on a parent-hash mismatch; or apply balances only at finalized depth.",
], source="src/schemas/filter.yaml")

ev("rpc-17-estimate-gas-revert", "estimateGas failed; send anyway", "An execution-reverted error from eth_estimateGas predicts an on-chain revert. It is not a gas-limit problem.",
f"""Users say our dApp sends transactions that fail on-chain and still cost them gas. The send path is:

    let gas;
    try {{
      gas = await publicClient.estimateGas(tx);
    }} catch {{
      gas = 500_000n; // estimation is flaky, use a safe default
    }}
    await walletClient.sendTransaction({{ ...tx, gas }});

What does an error from eth_estimateGas with code 3 mean, why is this fallback wrong, and how should the code handle estimation errors? {MD}""",
expect=[
 "answer.md explains that an eth_estimateGas error with code 3 (execution reverted) means the transaction reverts when executed against current state, so sending it with a fixed gas limit almost certainly reverts on-chain and the user still pays for the gas used.",
 "The fix stops the send on a revert error and shows the user the reason, decoding error.data (for example Error(string), Panic(uint256) or a custom error selector) instead of hiding it.",
 "It separates revert errors from transport or node errors (timeouts, rate limits, 5xx), and allows a retry only for the second group. An answer that keeps a blanket fallback gas limit for all errors fails.",
], source="tests/eth_estimateGas/estimate-call-abi-error.io")

ev("rpc-18-sendraw-not-included", "A hash is not a payment", "eth_sendRawTransaction returns a hash on pool admission. The transaction can still be dropped, replaced or reorged.",
f"""A checkout backend receives a signed transaction from the buyer's wallet, calls eth_sendRawTransaction, and when the node returns a transaction hash it marks the order paid and ships.

What does the returned hash actually guarantee? What must the backend check before it marks the order paid? {MD}""",
expect=[
 "answer.md explains that the hash only shows that this node accepted the transaction (for example into its pool), and that the transaction can still be dropped, never propagate, or be replaced by another transaction with the same nonce.",
 "It requires a receipt from eth_getTransactionReceipt with status 0x1 and a check of the payment itself: the recipient and the amount (value, or the token Transfer log), not just the status.",
 "It waits until the including block is safe or finalized, or a stated number of confirmations, before it ships, because an included transaction can still be reorged out.",
], source="src/eth/submit.yaml")

ev("rpc-19-pending-nonce", "Nonces behind a load balancer", "latest counts mined transactions only, and pending is one node's mempool.",
f"""A payout service sends 20 transactions in a loop from one hot wallet. For each one it calls eth_getTransactionCount(wallet, "latest") and uses the result as the nonce. Its RPC URL is a load balancer in front of three nodes. We see "nonce too low" and "replacement transaction underpriced" errors, and some payouts never arrive.

Explain the failure and give a nonce strategy that works. {MD}""",
expect=[
 "answer.md explains that 'latest' counts only transactions in mined blocks, so transactions sent before the next block reuse the same nonce and collide: later ones replace earlier ones or are rejected, and payouts are lost.",
 "It proposes a single local nonce manager per sender: read the starting nonce once, then assign sequential nonces locally and serialize sends.",
 "It notes that 'pending' reflects each node's own mempool, so behind a load balancer different nodes can return different pending counts; the fix must not depend on a fresh eth_getTransactionCount per send to a load-balanced URL (pinning one node and serializing sends also passes).",
], source="src/schemas/block.yaml")

ev("rpc-20-delegated-eoa", "An EOA with code", "After EIP-7702 an EOA can have code. Code checks, isContract and transfer() break for delegated users.",
f"""Since Pectra, two support problems keep coming in:
1. Our backend refuses withdrawals to "contracts", which it detects with eth_getCode(address) != "0x". Some ordinary users, who hold their own keys, are now flagged as contracts.
2. Our payout contract pays users with payable(user).transfer(amount). Payouts to some of those same users now revert.

Explain what changed and how to fix both. {MD}""",
expect=[
 "answer.md explains that an EIP-7702-delegated EOA has code: eth_getCode returns the 23-byte delegation designator 0xef0100 followed by the delegate address, so 'has code' no longer means 'is a contract without a private key'; the account still has its key and can sign.",
 "It explains that a call or value transfer to a delegated EOA runs the delegate contract's code, so transfer()'s 2300-gas stipend can be too little (or the delegate may have no payable receive/fallback), and the payout reverts. The fix sends value with a low-level call and handles failure, or uses pull payments.",
 "It fixes the detection, either by recognizing the 0xef0100 designator prefix instead of treating any code as a contract, or by dropping the code check as unreliable; and it notes that a delegation can be set, changed or cleared at any time, so a code check describes one moment and is not a durable property of the address.",
])

ev("rpc-21-getlogs-range", "Scanning history with eth_getLogs", "An eth_getLogs error is not 'no logs'. Chunk the range and stop at the head.",
f"""A script collects every Transfer from a token deployed three years ago:

    try {{
      return await rpc("eth_getLogs", [{{ address: TOKEN, fromBlock: "0x0", toBlock: "latest" }}]);
    }} catch {{
      return []; // no logs
    }}

On our provider it always returns []. A second version passes an explicit toBlock, computed as fromBlock + 100000, and also sometimes returns []. Explain what goes wrong and write a scanning approach that is correct. {MD}""",
expect=[
 "answer.md says that returning [] on error is wrong: the error means the query failed (for example the provider's block-range or result-size limit), not that there are no logs.",
 "It scans in chunks that shrink when the node rejects a range as too large. Starting from the token's deployment block instead of block 0 is a plus, not required.",
 "It caps toBlock at the current head (eth_blockNumber) or at the finalized block, because a toBlock above the head is an error (the spec returns -32602 'block range extends beyond current head block'), and it keeps a cursor so each block is scanned exactly once.",
], source="tests/eth_getLogs/filter-error-future-block-range.io")

ev("rpc-22-consistent-reads", "Three reads, one block", "Each 'latest' can be a different block. Pin a block hash (EIP-1898).",
f"""A dashboard prices an LP token from three reads: eth_call getReserves() at "latest", eth_call totalSupply() at "latest" 300 ms later, and eth_getBalance of the pool at "latest". The RPC URL is a load balancer. The computed price sometimes spikes for one refresh and then returns to normal.

Why, and how do you make the three reads come from the same state? {MD}""",
expect=[
 "answer.md explains that each 'latest' request can resolve to a different block, because a new block arrives between calls or a different backend node answers, so the three values come from different states.",
 "It fixes this by pinning every read to the same block by hash, as an EIP-1898 block object {\"blockHash\": ...} (requireCanonical is optional), or by combining the reads into one eth_call through Multicall3. A pinned block number passes only if the answer also guards against a reorg (for example, checks the block hash); a bare number fails, because after a reorg the same number can name a different block.",
], source="src/schemas/block.yaml")

ev("rpc-23-simulate-approve-swap", "Preview two transactions", "Separate eth_calls do not share state. eth_simulateV1 chains calls in one block.",
f"""A wallet previews a two-step action: approve(router, 100 USDC), then router.swap(...). The preview runs eth_call for each transaction separately at "latest". The swap preview always reverts with "insufficient allowance", even though the approve preview succeeds.

Explain why, and how to preview the pair correctly with standard JSON-RPC. {MD}""",
expect=[
 "answer.md explains that each eth_call runs alone against the state of the given block and changes nothing, so the approve's effect is not visible to the separate swap call.",
 "It uses eth_simulateV1 with both calls in order in one blockStateCalls entry, so state carries over from the approve to the swap; setting validation true (nonce, fee and balance checks) or traceTransfers true is a plus, not required. A state-override eth_call that writes the allowance slot counts only if it is presented as an approximation.",
], source="src/eth/execute.yaml")

ev("rpc-24-get-proof", "Verify a balance with eth_getProof", "Account proof against stateRoot, storage proof against storageHash, slot from the mapping.",
f"""A light wallet shows a user's balance of a token that is a plain, non-upgradeable OpenZeppelin ERC20, with its _balances mapping at storage slot 0. The wallet must not trust its RPC provider. It has a block hash it trusts from a light client. Describe, step by step, how to verify the balance with eth_getProof and eth_getBlockByHash. {MD}""",
expect=[
 "answer.md fetches the header for the trusted block hash, checks that the header hashes to that hash (keccak256 of the RLP-encoded header), and takes its stateRoot.",
 "It calls eth_getProof for the token contract address with the storage slot of balances[user], at that block, and verifies accountProof against stateRoot (a Merkle-Patricia path keyed by keccak256(address)) to obtain the contract's storageHash.",
 "It verifies the storageProof entry against that storageHash, and derives the slot for the balance as keccak256(abi.encode(user, 0)), the mapping entry for slot 0.",
], source="src/eth/state.yaml")

ev("rpc-25-fee-fields", "Fee fields from JSON-RPC", "eth_gasPrice is a legacy price. Type-2 fees come from base fee and tip; blob fees from eth_blobBaseFee.",
f"""A bot builds type-2 transactions with maxFeePerGas = maxPriorityFeePerGas = the result of eth_gasPrice. It overpays tips when the chain is quiet and gets stuck when the base fee spikes. It must also start sending type-3 blob transactions.

How should the bot set each fee field, using which JSON-RPC methods? {MD}""",
expect=[
 "answer.md explains that eth_gasPrice returns one legacy price (roughly base fee plus a suggested tip), so using it as the tip overpays the proposer, and using it as maxFeePerGas leaves no headroom when the base fee rises.",
 "It sets maxPriorityFeePerGas from eth_maxPriorityFeePerGas or from eth_feeHistory reward percentiles, and sets maxFeePerGas from the next block's base fee (the last baseFeePerGas entry of eth_feeHistory, or the pending block) with headroom, for example 2 x base fee + tip.",
 "For blob transactions it sets maxFeePerBlobGas from eth_blobBaseFee (or baseFeePerBlobGas from eth_feeHistory) with headroom, and notes that blob gas is priced in a separate fee market from execution gas.",
], source="src/eth/fee_market.yaml")

os.makedirs(os.path.join(OUT, "rpc"), exist_ok=True)
for d in E:
    p = os.path.join(OUT, d["pillar"], d["id"] + ".yaml")
    with open(p, "w") as fh: yaml.dump(d, fh, sort_keys=False, allow_unicode=True, width=110)
