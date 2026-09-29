#!/usr/bin/env python3
"""Run the multiple-choice version of ethevals (mc/questions.json) and score it.

This is how decision models that can't write text get measured, next to LLMs on the
same questions.

  python3 run_mc.py --name jev-1.13 --backend jev            # TYPESAFE_API_KEY
  python3 run_mc.py --name sage-1.1 --backend sage           # SAGE_API_KEY
  python3 run_mc.py --name haiku-4.5 --backend claude --model haiku
  python3 run_mc.py --name x --cmd 'my-llm --stdin'          # prompt on stdin, reply on stdout
  python3 run_mc.py --report                                 # table of every mc/results/*.json

Writes mc/results/<name>.json. Every row keeps the pick, the probability the model gave
the right answer (decision models only), and the time taken.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, re, statistics, sys, time, urllib.error, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
QUESTIONS = os.path.join(ROOT, "mc", "questions.json")
RESULTS = os.path.join(ROOT, "mc", "results")
PILLARS = ["concepts", "transactions", "building", "security"]
LETTERS = "ABCD"
INSTRUCTIONS = "Which option correctly answers the question?"

sys.path.insert(0, ROOT)
import run  # noqa: E402  (child_env, run_cmd)


def load_env():
    p = os.path.join(ROOT, ".env")
    if os.path.exists(p):
        for line in open(p):
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


def post(url, key, body, timeout=60):
    data = json.dumps(body).encode()
    for attempt in range(5):
        req = urllib.request.Request(url, data=data, headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "User-Agent": "ethevals/1.0"})  # Sage's WAF 403s the default Python UA
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 529) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")


# ------------------------------------------------------------------ backends
# Each returns (pick or None, {letter: probability} or None, raw note).

def ask_jev(q, model):
    body = {"model": model or "jev-latest", "state": {"question": q["stem"]},
            "questions": {"answer": {"type": "choice", "instructions": INSTRUCTIONS, "criteria": q["options"]}}}
    r = post("https://api.typesafe.ai/v1/systemone", os.environ["TYPESAFE_API_KEY"], body)
    a = r["answers"]["answer"]
    return a["choice"], a["probabilities"], {"model": r.get("model"), "tokens": (r.get("usage") or {}).get("input_tokens")}


def ask_sage(q, model, reasoning="auto"):
    body = {"content": {"kind": "text", "value": q["stem"]}, "reasoning": reasoning,
            "question": {"id": "answer", "kind": "choice", "instructions": INSTRUCTIONS,
                         "options": [{"option": L, "description": q["options"][L]} for L in LETTERS]}}
    r = post("https://sage.levanto.ai/decide", os.environ["SAGE_API_KEY"], body)
    res = r["result"]
    probs = {p["option"]: p["probability"] for p in res["probabilities"]}
    meta = r.get("meta") or {}
    return res.get("chosen"), probs, {"model": meta.get("model"), "reasoned": (meta.get("reasoning") or {}).get("ran")}


def ask_cmd(q, cmd):
    prompt = (q["stem"] + "\n\n" + "\n".join(f"{L}) {q['options'][L]}" for L in LETTERS)
              + "\n\nReply with only the letter of the right option.")
    out, err, rc, _ = run.run_cmd(cmd, prompt, ROOT, 600)
    if rc != 0 or run.DEAD_RE.search(out or ""):
        raise RuntimeError(f"rc={rc}: {(err or out)[:200]}")
    return parse_letter(out), None, {"reply": out.strip()[:300]}


def parse_letter(out):
    """The letter a free-text reply picked: a bare letter, a leading "B)", or "Answer: B"."""
    t = out.strip().strip("*`").strip()
    m = (re.fullmatch(r"\(?([ABCD])\)?\.?", t) or re.match(r"\(?([ABCD])[).:\n]", t)
         or re.search(r"(?i)answer(?: is)?[:\s*]+\(?([ABCD])\b", t) or re.search(r"\*\*\(?([ABCD])\)?[).:]?\*\*", t))
    return m.group(1) if m else None


# ------------------------------------------------------------------ scoring

def summarize(rows):
    def acc(rs): return round(100 * sum(r["correct"] for r in rs) / len(rs), 1) if rs else None
    s = {"n": len(rows), "accuracy": acc(rows),
         "pillars": {p: acc([r for r in rows if r["pillar"] == p]) for p in PILLARS},
         "no_answer": sum(r["pick"] is None for r in rows),
         "median_ms": round(statistics.median(r["ms"] for r in rows)) if rows else None}
    pr = [r for r in rows if r.get("p_right") is not None]
    if pr:
        # Brier over all four options: 0 is perfect, 0.75 is "evenly unsure", 2 is confidently wrong.
        s["brier"] = round(statistics.mean(
            sum((r["probs"].get(L, 0) - (L == r["answer"])) ** 2 for L in LETTERS) for r in pr), 3)
        s["mean_p_right"] = round(statistics.mean(r["p_right"] for r in pr), 3)
        # Sage abstains ("too close to call") by design; its top-probability option is the fair comparison.
        s["top_pick_accuracy"] = acc([{**r, "correct": max(r["probs"], key=r["probs"].get) == r["answer"]} for r in pr])
    return s


def report():
    rows = []
    for f in sorted(glob.glob(os.path.join(RESULTS, "*.json"))):
        d = json.load(open(f))
        s = d["summary"]
        rows.append((s["accuracy"], d["name"], s, d["questions_hash"]))
    cur = qhash(json.load(open(QUESTIONS)))
    print(f"{'name':24} {'acc':>5} {'top':>5}  {'conc':>5} {'tx':>5} {'build':>5} {'sec':>5}  {'brier':>5} {'p(right)':>8} {'none':>4} {'ms':>6}")
    for acc, name, s, h in sorted(rows, key=lambda r: -(r[0] or 0)):
        p = s["pillars"]
        f = lambda v: "-" if v is None else v
        print(f"{name:24} {f(acc):>5} {f(s.get('top_pick_accuracy')):>5}  {f(p['concepts']):>5} {f(p['transactions']):>5} {f(p['building']):>5} {f(p['security']):>5}  "
              f"{s.get('brier', '-'):>5} {s.get('mean_p_right', '-'):>8} {s['no_answer']:4} {s['median_ms']:6}"
              + ("" if h == cur else "  (old question set)"))


def qhash(qs):
    return hashlib.sha256(json.dumps(qs, sort_keys=True).encode()).hexdigest()[:12]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name")
    ap.add_argument("--backend", choices=["jev", "sage", "claude", "codex"])
    ap.add_argument("--model")
    ap.add_argument("--reasoning", default="auto", help="sage only: auto | off | on")
    ap.add_argument("--cmd")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    if a.report:
        return report()
    load_env()
    qs = json.load(open(QUESTIONS))
    if a.only:
        qs = [q for q in qs if any(o in q["id"] for o in a.only)]

    if a.backend == "jev":
        ask, cmd = (lambda q: ask_jev(q, a.model)), f"typesafe {a.model or 'jev-latest'}"
    elif a.backend == "sage":
        ask, cmd = (lambda q: ask_sage(q, a.model, a.reasoning)), f"sage /decide reasoning={a.reasoning}"
    else:
        cmd = a.cmd or run.EXECUTORS[a.backend](a.model)
        ask = lambda q: ask_cmd(q, cmd)

    def one(q):
        t0 = time.time()
        try:
            pick, probs, note = ask(q)
            err = None
        except Exception as e:
            pick, probs, note, err = None, None, None, str(e)[:300]
        row = {"id": q["id"], "pillar": q["pillar"], "answer": q["answer"], "pick": pick,
               "correct": pick == q["answer"], "ms": round((time.time() - t0) * 1000)}
        if probs:
            row["probs"] = {L: round(float(probs.get(L, 0)), 4) for L in LETTERS}
            row["p_right"] = row["probs"][q["answer"]]
        if note: row["note"] = note
        if err: row["error"] = err
        return row

    with cf.ThreadPoolExecutor(a.concurrency) as pool:
        rows = list(pool.map(one, qs))
    errors = [r for r in rows if r.get("error")]
    for r in errors[:5]:
        print(f"error {r['id']}: {r['error']}", file=sys.stderr)

    out = {"name": a.name, "backend": a.backend or "cmd", "model": a.model, "cmd": cmd,
           "questions_hash": qhash(json.load(open(QUESTIONS))), "errors": len(errors),
           "summary": summarize(rows), "rows": rows}
    if a.name and not a.only:
        os.makedirs(RESULTS, exist_ok=True)
        json.dump(out, open(os.path.join(RESULTS, f"{a.name}.json"), "w"), indent=1)
    print(json.dumps(out["summary"], indent=1))


if __name__ == "__main__":
    main()
