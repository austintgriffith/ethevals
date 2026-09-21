#!/usr/bin/env python3
"""Roll evals/ and results/ into the two JSON files the site reads:
  evals/index.json    the catalog (pillar, title, kind, how it is graded, source)
  results/index.json  one row per result file, with per-pillar scores
Run after adding an eval or a result. Both files are committed."""
import datetime as dt, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run import load_evals, manifest, PILLARS, ROOT

PILLAR_META = {
    "concepts": ("Concepts", "What gets built on Ethereum and why it holds up. Incentive design, the walkaway test, decentralization, MEV, EIP-1559, EIP-712, the fork roadmap."),
    "transactions": ("Transactions", "Reading the chain. Calldata, selectors, ABIs, events, receipts, gas, what a block explorer is really showing you."),
    "building": ("Building", "Shipping a dApp real users can touch. Approvals, decimals, USD context, RPCs, indexing, keys, and the whole way to production."),
    "security": ("Security", "Everyone catches reentrancy. Inflation attacks, stale oracles, signature replay, upgrade collisions, rounding, and the rest."),
}

def summary(e):
    if e.get("summary"): return e["summary"]
    t = re.sub(r"\s+", " ", e["prompt"]).strip()
    t = re.sub(r'\s*(End your reply|Reply with JSON|Write your answer|Answer with only).*$', "", t)
    return (t[:170] + "…") if len(t) > 170 else t

def main():
    evals = load_evals()
    cat = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "manifest": manifest(evals),
           "pillars": [{"id": p, "name": PILLAR_META[p][0], "desc": PILLAR_META[p][1], "count": sum(e["pillar"] == p for e in evals)} for p in PILLARS],
           "evals": [{"id": e["id"], "pillar": e["pillar"], "title": e["title"], "kind": e["kind"], "graded": "deterministic" if "grader" in e else "judge",
                      "summary": summary(e), "source": e.get("source", {})} for e in evals]}
    json.dump(cat, open(os.path.join(ROOT, "evals", "index.json"), "w"), indent=1)
    runs = []
    for f in sorted(glob.glob(os.path.join(ROOT, "results", "*.json"))):
        if f.endswith("index.json"): continue
        d = json.load(open(f))
        rows = [r for r in d.get("rows", []) if not r.get("dead") and not r.get("ungraded")]
        runs.append({k: d.get(k) for k in ("name", "model", "harness", "skill", "started", "manifest", "pillars", "total")}
                    | {"file": os.path.relpath(f, ROOT), "evals_run": len(rows), "verdicts": {r["id"]: bool(r["pass"]) for r in rows}})
    runs.sort(key=lambda r: -(r["total"]["pass"] if r.get("total") else 0))
    json.dump({"generated": cat["generated"], "manifest": cat["manifest"], "runs": runs}, open(os.path.join(ROOT, "results", "index.json"), "w"), indent=1)
    print(f"evals/index.json: {len(evals)} evals; results/index.json: {len(runs)} runs; manifest {cat['manifest']}")

if __name__ == "__main__":
    main()
