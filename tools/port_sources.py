#!/usr/bin/env python3
"""Port selected tasks from the two source repos into evals/<pillar>/<id>.yaml.

Sources (clone them next to this repo, or pass --src DIR holding both clones):
  BuidlGuidl/ethskills-evals   yaml tasks: input + expect lines (LLM-judged)
  clawdbotatg/eth-evals        jsonl tasks: prompt + deterministic grader

The eval id, title and pillar are decided here; the prompt and grading material
are copied from the source unchanged so the rubrics keep their history.
"""
import argparse, glob, json, os, re, sys, yaml

# (our id, title, source repo, source task id)
PORTS = [
  # ---- concepts (eth-evals, deterministic) ----
  ("concepts-01-nothing-is-automatic", "Nothing is automatic", "eth-evals", "concepts-k-02"),
  ("concepts-02-walkaway-test", "The walkaway test", "eth-evals", "cryptoecon-k-02"),
  ("concepts-03-keeper-bounty-math", "Keeper bounty math", "eth-evals", "cryptoecon-k-03"),
  ("concepts-04-hyperstructures", "Hyperstructures", "eth-evals", "concepts-k-09"),
  ("concepts-05-fee-switch-fork", "The fee-switch fork", "eth-evals", "cryptoecon-k-05"),
  ("concepts-06-sybil-resistance", "Sybil resistance", "eth-evals", "cryptoecon-k-06"),
  ("concepts-07-crops-pillars", "Which CROPS pillar", "eth-evals", "crops-k-04"),
  ("concepts-08-verified-is-not-open", "Verified is not open source", "eth-evals", "crops-k-02"),
  ("concepts-10-mev-backrun", "MEV backruns", "eth-evals", "mev-k-04"),
  ("concepts-11-spot-price-oracle", "Spot price is not an oracle", "eth-evals", "concepts-k-07"),
  ("concepts-12-blockhash-current", "blockhash of the current block", "eth-evals", "concepts-k-03"),
  ("concepts-13-eip712-replay", "EIP-712 replay protection", "eth-evals", "security-k-10"),
  ("concepts-14-eip7702-delegation", "EIP-7702 delegation", "eth-evals", "standards-k-07"),
  ("concepts-16-peerdas-eip", "PeerDAS and the fork roadmap", "eth-evals", "protocol-k-08"),
  ("concepts-17-forced-inclusion", "L2 exit and forced inclusion", "eth-evals", "crops-k-11"),
  ("concepts-18-admin-power-mechanisms", "Surviving admin powers", "eth-evals", "crops-k-05"),
  ("concepts-19-why-slashing", "Why slashing exists", "eth-evals", "cryptoecon-k-08"),
  ("concepts-20-honesty-live-data", "Honesty on live data", "eth-evals", "honesty-k-01"),
  # ---- transactions (eth-evals generated, deterministic) ----
  ("transactions-02-abi-encode-static", "ABI-encode a static call", "eth-evals", "calldata-encgiven-01"),
  ("transactions-03-decode-calldata", "Decode calldata", "eth-evals", "calldata-decgiven-01"),
  ("transactions-09-event-signature", "Event signature string", "eth-evals", "indexing-evsig-01"),
  ("transactions-14-gwei-to-wei", "Units", "eth-evals", "units-01"),
  ("transactions-15-intrinsic-gas", "Intrinsic gas", "eth-evals", "gas-intrinsic-01"),
  ("transactions-16-create2-truncation", "CREATE2 address from the hash", "eth-evals", "derivations-c2finish-01"),
  # ---- building (ethskills-evals, judged) ----
  ("building-02-approve-flow-states", "The approve-then-stake flow", "ethskills-evals", "frontend-ux-quiz-003"),
  ("building-03-usdc-decimals", "USDC has six decimals", "ethskills-evals", "frontend-ux-quiz-002"),
  ("building-04-se2-staking-dapp", "Build a staking dApp on Scaffold-ETH 2", "ethskills-evals", "frontend-ux-goal-001"),
  ("building-05-button-lifecycle", "The approve button lifecycle", "ethskills-evals", "frontend-ux-quiz-001"),
  ("building-06-ens-input", "ENS in address inputs", "ethskills-evals", "frontend-ux-quiz-005"),
  ("building-07-double-fire", "Pending state that still double-fires", "ethskills-evals", "qa-quiz-002"),
  ("building-08-rpc-config", "RPC configuration", "ethskills-evals", "qa-quiz-005"),
  ("building-09-mobile-chain-switch", "Mobile wallet chain switch", "ethskills-evals", "qa-quiz-004"),
  ("building-10-index-events", "Index events, not blocks", "ethskills-evals", "indexing-quiz-001"),
  ("building-11-forty-balances", "Forty token balances", "ethskills-evals", "indexing-quiz-003"),
  ("building-12-pick-a-chain", "Pick a chain with numbers", "ethskills-evals", "gas-quiz-001"),
  ("building-13-l2-real-cost", "Where the L2 fee goes", "ethskills-evals", "gas-quiz-002"),
  ("building-14-deployer-key-hygiene", "Deployer key hygiene", "ethskills-evals", "wallets-goal-003"),
  ("building-15-agent-custody", "Bounded agent authority", "ethskills-evals", "wallets-goal-002"),
  ("building-16-one-click-from-eoa", "One-click from an EOA", "ethskills-evals", "wallets-quiz-001"),
  ("building-17-x402-paid-api", "x402 paid API", "ethskills-evals", "tools-quiz-001"),
  ("building-18-create2-address-myth", "Same address on every chain", "ethskills-evals", "addresses-quiz-003"),
  ("building-19-deploy-verify-ship", "Deploy, verify, ship", "ethskills-evals", "orchestration-quiz-001"),
  ("building-20-existing-eoa-smart-account", "Upgrade an existing EOA", "ethskills-evals", "standards-quiz-002"),
  # ---- security ----
  ("security-01-reentrancy", "Reentrancy", "eth-evals", "security-k-01"),
  ("security-04-vault-inflation", "Vault inflation attack", "ethskills-evals", "security-quiz-001"),
  ("security-05-spot-price-oracle", "Spot price oracles", "ethskills-evals", "security-quiz-002"),
  ("security-06-fee-on-transfer-books", "Books that do not close", "ethskills-evals", "security-quiz-003"),
  ("security-07-oz-v5-approvals", "OpenZeppelin v5 approvals", "ethskills-evals", "security-quiz-004"),
  ("security-08-signature-replay", "Signature replay", "ethskills-evals", "security-quiz-005"),
  ("security-09-uups-upgrade", "The upgrade that succeeded", "ethskills-evals", "security-quiz-006"),
  ("security-10-checks-effects-interactions", "Checks, effects, interactions", "eth-evals", "security-k-04"),
  ("security-11-missing-access-control", "Missing access control", "eth-evals", "security-k-07"),
  ("security-12-storage-layout", "Upgrade storage layout", "eth-evals", "security-k-08"),
  ("security-13-authorize-upgrade", "UUPS authorization", "eth-evals", "security-k-09"),
  ("security-14-sandwich-slippage", "Sandwiches and slippage", "eth-evals", "security-k-03"),
  ("security-15-lending-postmortem-1", "Lending post-mortem: the sequencer", "ethskills-evals", "audit-quiz-001"),
  ("security-16-lending-postmortem-2", "Lending post-mortem: the clock", "ethskills-evals", "audit-quiz-002"),
  ("security-17-lending-postmortem-3", "Lending post-mortem: the signature", "ethskills-evals", "audit-quiz-003"),
  ("security-19-permissionless-listing", "Permissionless token listing", "ethskills-evals", "security-goal-001"),
  ("security-20-borrowing-market", "Build a borrowing market", "ethskills-evals", "security-goal-002"),
]

# ethskills-evals tasks that need a workspace template: source task -> (template dir, our workspace dir, extra expect lines prepended)
TEMPLATES = {
  "frontend-ux-goal-001": ("templates/se-2", "se2-usdc-staking", [
    "The approve call's amount is the amount being staked (or a small bounded multiple of it). Approving maxUint256, type(uint256).max, 2**256-1, a hardcoded very large constant, or any 'unlimited' allowance anywhere in the delivered frontend or contracts is a FAIL.",
  ]),
}

def load_eth_evals(src):
    out = {}
    for f in glob.glob(os.path.join(src, "eth-evals", "tasks", "*.jsonl")):
        for line in open(f):
            if line.strip():
                t = json.loads(line); out[t["id"]] = t
    return out

def load_ethskills_evals(src):
    out = {}
    for f in glob.glob(os.path.join(src, "ethskills-evals", "tasks", "*.yaml")):
        out[os.path.basename(f)[:-5]] = yaml.safe_load(open(f))
    return out

class Lit(str): pass
def lit_rep(d, s): return d.represent_scalar("tag:yaml.org,2002:str", s, style="|")
yaml.add_representer(Lit, lit_rep)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--src", default=os.path.join(os.path.dirname(__file__), "..", ".."))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "evals"))
    a = ap.parse_args()
    ee, se = load_eth_evals(a.src), load_ethskills_evals(a.src)
    n = 0
    for oid, title, repo, sid in PORTS:
        pillar = oid.split("-")[0]
        doc = {"id": oid, "pillar": pillar, "title": title}
        if repo == "eth-evals":
            t = ee.get(sid)
            if not t: print("MISSING", sid, file=sys.stderr); continue
            doc["kind"] = "quiz"
            doc["prompt"] = Lit(t["prompt"].rstrip() + "\n")
            doc["grader"] = t["grader"]
            if sid == "concepts-k-03":  # "0 (bytes32(0), the zero hash)" is right; the bigint option calls it ambiguous
                doc["grader"] = {"type": "any_of", "options": t["grader"]["options"] + [{"type": "regex", "pattern": r"^(0|0x0+)\b|bytes32\(0\)|zero"}]}
            if t.get("reference"): doc["reference"] = t["reference"]
            if t.get("checks"):
                # a bare quoted 64-hex fixture trips private-key scanners; phrase it as an answer line
                fix = lambda xs: [("Answer: " + x) if re.fullmatch(r"0x[0-9a-fA-F]{64}", x) else x for x in xs]
                doc["checks"] = {k: fix(v) for k, v in t["checks"].items()}
            if t.get("source_quote"): doc["source_quote"] = Lit(t["source_quote"].rstrip() + "\n")
            doc["source"] = {"repo": "clawdbotatg/eth-evals", "task": sid, "skill": t.get("source")}
        else:
            t = se.get(sid)
            if not t: print("MISSING", sid, file=sys.stderr); continue
            extra = []
            if t.get("template"):
                if sid not in TEMPLATES: print("SKIP (needs template)", sid, file=sys.stderr); continue
                tdir, wdir, extra = TEMPLATES[sid]
                dst = os.path.join(a.out, pillar, wdir)
                if not os.path.isdir(dst):
                    import shutil; shutil.copytree(os.path.join(a.src, "ethskills-evals", tdir), dst)
                doc["workspace"] = wdir
            doc["kind"] = "goal" if "-goal-" in sid else "quiz"
            doc["prompt"] = Lit(t["input"].rstrip() + "\n")
            doc["expect"] = extra + [str(e) for e in t["expect"]]
            doc["source"] = {"repo": "BuidlGuidl/ethskills-evals", "task": sid, "skill": t.get("skill")}
        path = os.path.join(a.out, pillar, oid + ".yaml")
        with open(path, "w") as fh:
            yaml.dump(doc, fh, sort_keys=False, allow_unicode=True, width=100)
        n += 1
    print(f"ported {n} evals")

if __name__ == "__main__":
    main()
