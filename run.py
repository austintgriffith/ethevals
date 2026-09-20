#!/usr/bin/env python3
"""ethevals runner: run every eval against an executor, grade, write results/<name>.json.

  python3 run.py --list
  python3 run.py --self-test
  python3 run.py --name fable --executor claude --model fable
  python3 run.py --name gpt --executor codex --model gpt-5.6
  python3 run.py --name x --cmd 'my-agent --stdin' --judge-cmd 'claude -p --model sonnet'
  python3 run.py --name fable+ethskills --executor claude --model fable --skill https://ethskills.com/SKILL.md

Executor contract: the prompt arrives on stdin, the reply is stdout, cwd is a fresh
workspace directory the executor may write files into. Quiz evals are graded on the
reply (deterministic grader) or on reply + files (LLM judge). Goal evals are graded
on the files the executor left in the workspace.
"""
import argparse, concurrent.futures as cf, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, tempfile, time, urllib.request
import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
EVALS_DIR = os.path.join(ROOT, "evals")
RESULTS_DIR = os.path.join(ROOT, "results")
PILLARS = ["concepts", "transactions", "building", "security"]
EXEC_TIMEOUT = 1800
JUDGE_TIMEOUT = 600
MAX_FILE_BYTES = 60_000
MAX_EVIDENCE_BYTES = 400_000

# ------------------------------------------------------------------ evals

def load_evals(pillar=None, only=None, limit=None):
    out = []
    for p in PILLARS:
        if pillar and p != pillar: continue
        d = os.path.join(EVALS_DIR, p)
        for f in sorted(os.listdir(d)):
            if not f.endswith(".yaml"): continue
            e = yaml.safe_load(open(os.path.join(d, f)))
            e["_dir"] = d
            if only and not any(o in e["id"] for o in only): continue
            out.append(e)
    return out[:limit] if limit else out

def manifest(evals):
    h = hashlib.sha256()
    for e in evals:
        h.update(json.dumps({k: v for k, v in e.items() if not k.startswith("_")}, sort_keys=True).encode())
    h.update(open(__file__, "rb").read())
    return h.hexdigest()[:12]

# ------------------------------------------------------------------ deterministic graders (ported from clawdbotatg/eth-evals, MIT)

def norm(t, casefold=True):
    t = (t or "").strip().strip("`*").strip()
    t = re.sub(r"\s+", " ", t).strip().rstrip(".").strip().strip("\"'*").strip()
    return t.casefold() if casefold else t

def lines(r): return [l.strip() for l in (r or "").strip().splitlines() if l.strip()]

def ans_line(r):
    found = None
    for l in (r or "").strip().splitlines():
        m = re.match(r"\s*[*#>\s]*answer\s*[:=]\s*(.+?)\s*$", l, re.I)
        if m: found = m.group(1)
    if found is None:
        m = re.search(r"answer\s*[:=]\s*(.+?)\s*$", r or "", re.I | re.M)
        if m: found = m.group(1)
    if found is not None: return found.strip().strip("*").strip()
    ls = lines(r); return ls[-1] if ls else ""

def extract_num(r):
    a = ans_line(r)
    for scope in (a, r or ""):
        nums = re.findall(r"-?\$?\d[\d,]*\.?\d*(?:e[+-]?\d+)?", scope, re.I)
        if nums:
            pick = nums[0] if scope is a else nums[-1]
            return float(pick.replace("$", "").replace(",", ""))
    return None

_INT_RE = re.compile(r"(?:0x[0-9a-fA-F][0-9a-fA-F_]*|(?<![\w-])-\d[\d_,]*|\d[\d_,]*)")
def extract_bigints(r):
    out = []
    for m in _INT_RE.finditer(r or ""):
        s = m.group(0).replace("_", "").replace(",", "")
        try: out.append(int(s, 16) if s.lower().startswith("0x") else int(s))
        except ValueError: pass
    return out

def jload(r):
    r = (r or "").strip()
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", r, re.S)
    for c in ([fenced[-1]] if fenced else []) + [r]:
        c = c.strip()
        try: return json.loads(c)
        except Exception: pass
        for op, cl in (("{", "}"), ("[", "]")):
            i, j = c.find(op), c.rfind(cl)
            if 0 <= i < j:
                try: return json.loads(c[i:j + 1])
                except Exception: pass
    raise ValueError("no JSON found in response")

def jmatch(exp, got):
    if isinstance(exp, bool): return isinstance(got, bool) and exp == got
    if isinstance(exp, (int, float)):
        if isinstance(got, str):
            try: got = int(got, 16) if got.lower().startswith("0x") else float(got)
            except ValueError: return False
        return isinstance(got, (int, float)) and not isinstance(got, bool) and abs(exp - got) < 1e-6
    if isinstance(exp, str):
        if not isinstance(got, str): return False
        if exp.startswith("~"): return exp[1:].casefold() in got.casefold()
        return norm(exp) == norm(got)
    if isinstance(exp, list): return isinstance(got, list) and len(exp) == len(got) and all(jmatch(e, g) for e, g in zip(exp, got))
    if isinstance(exp, dict): return isinstance(got, dict) and all(k in got and jmatch(v, got[k]) for k, v in exp.items())
    if exp is None: return got is None
    return exp == got

_NEG_RE = re.compile(r"(?i)(?<![\w-])(not|isn'?t|aren'?t|doesn'?t|don'?t|won'?t|wasn'?t|weren'?t|never|cannot|can'?t|neither|nor|rather than|instead of|no longer|wrong|incorrect)(?![\w-])|!=|≠")

def _grade_one(g, resp):
    t = g["type"]
    if t == "numeric":
        v = extract_num(resp); ok = v is not None and abs(v - g["expect"]) <= g.get("tol", 1e-6)
        return ok, f"got {v}"
    if t == "bigint":
        exp = g["expect"]
        if isinstance(exp, str): exp = int(exp, 16) if exp.lower().startswith("0x") else int(exp)
        a_ints = extract_bigints(ans_line(resp))
        if a_ints:
            if len(set(a_ints)) > 1: return False, f"ambiguous: multiple integers {sorted(set(a_ints))[:4]}"
            return a_ints[0] == exp, f"got {a_ints[0]}"
        r_ints = extract_bigints(resp)
        return bool(r_ints) and r_ints[-1] == exp, f"got {r_ints[-1] if r_ints else None}"
    if t == "exact":
        cf_ = not g.get("case_sensitive", False)
        cands = [norm(resp, cf_)]
        ls = lines(resp)
        if ls: cands.append(norm(ls[-1], cf_))
        cands.append(norm(ans_line(resp), cf_))
        return norm(g["expect"], cf_) in cands, f"got {cands[-1][:80]!r}"
    if t == "regex":
        scope = ans_line(resp) if g.get("on", "answer") == "answer" else resp
        return bool(re.search(g["pattern"], scope, 0 if g.get("case_sensitive") else re.I)), f"answer {scope[:80]!r}"
    if t == "regex_all":
        scope = ans_line(resp) if g.get("on", "answer") == "answer" else resp
        flags = 0 if g.get("case_sensitive") else re.I
        misses = [p for p in g["patterns"] if not re.search(p, scope, flags)]
        return not misses, (f"missing {misses[:3]}" if misses else "")
    if t == "json":
        got = jload(resp); ok = jmatch(g["expect"], got)
        return ok, "" if ok else f"got {json.dumps(got)[:120]}"
    if t == "any_of":
        details = []
        for sub in g["options"]:
            ok, d = _grade_one(sub, resp)
            if ok: return True, ""
            details.append(d)
        return False, ("; ".join(details))[:140]
    raise ValueError(f"unknown grader type {t}")

def grade_deterministic(ev, resp):
    try:
        ok, detail = _grade_one(ev["grader"], resp)
        if ok and _NEG_RE.search(ans_line(resp)) and not _NEG_RE.search(ev.get("reference", "")):
            return False, f"negated answer line: {ans_line(resp)[:80]!r}"
        return ok, detail
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:140]

# ------------------------------------------------------------------ process plumbing

SCRUB = re.compile(r"^(CLAUDECODE$|CLAUDE_CODE_|ANTHROPIC_API_KEY$|CLAUDE_AGENT_|CODEX_)")
def child_env():
    nested = "CLAUDECODE" in os.environ
    env = {k: v for k, v in os.environ.items() if not SCRUB.match(k)}
    if nested: env.pop("ANTHROPIC_BASE_URL", None)  # a harness proxy, not ours
    return env

def run_cmd(cmd, stdin, cwd, timeout):
    t0 = time.time()
    try:
        p = subprocess.run(cmd, shell=True, input=stdin, capture_output=True, text=True, cwd=cwd, env=child_env(), timeout=timeout)
        return p.stdout, p.stderr, p.returncode, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return (e.stdout or ""), f"timeout after {timeout}s", -1, time.time() - t0

EXECUTORS = {
    "claude": lambda model: f"claude -p --model {model} --dangerously-skip-permissions --strict-mcp-config",
    "codex":  lambda model: f"codex exec --model {model} --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check -o .ethevals-reply.txt - >/dev/null 2>&1; cat .ethevals-reply.txt",
    "opencode": lambda model: f"opencode run --model {model}",
}

JUDGE_DEFAULT = "claude -p --model sonnet --strict-mcp-config --disallowedTools Bash,Edit,Write,WebFetch,WebSearch"

# ------------------------------------------------------------------ workspace + evidence

def seed_workspace(ev, skill_text):
    ws = tempfile.mkdtemp(prefix="ethevals-")
    src = ev.get("workspace")
    if src:
        shutil.copytree(os.path.join(ev["_dir"], src), ws, dirs_exist_ok=True)
    if skill_text:
        open(os.path.join(ws, "SKILL.md"), "w").write(skill_text)
        note = "Read SKILL.md in this directory before you start and follow it.\n"
        for f in ("CLAUDE.md", "AGENTS.md"):
            open(os.path.join(ws, f), "a").write(note)
    seed = snapshot(ws)
    return ws, seed

SKIP_NAMES = {".git", "node_modules", ".ethevals-reply.txt", ".claude", ".codex"}
def snapshot(ws):
    out = {}
    for base, dirs, files in os.walk(ws):
        dirs[:] = [d for d in dirs if d not in SKIP_NAMES]
        for f in files:
            if f in SKIP_NAMES: continue
            p = os.path.join(base, f); rel = os.path.relpath(p, ws)
            try:
                data = open(p, "rb").read(MAX_FILE_BYTES + 1)
            except OSError:
                continue
            out[rel] = data.decode("utf-8", "replace")[:MAX_FILE_BYTES]
    return out

def evidence(ev, reply, seed, after):
    parts = []
    changed = {k: v for k, v in after.items() if seed.get(k) != v}
    if ev["kind"] == "quiz" and reply.strip():
        parts.append("REPLY (stdout):\n" + reply.strip())
    if changed:
        for k in sorted(changed):
            parts.append(f"FILE {k}:\n" + changed[k])
    elif ev["kind"] == "goal":
        parts.append("(the executor wrote no files)")
    text = "\n\n".join(parts) or "(empty reply)"
    return text[:MAX_EVIDENCE_BYTES]

# ------------------------------------------------------------------ judge

def judge(ev, evid, judge_cmd):
    exp = ev["expect"]
    prompt = "\n".join([
        "You are grading one run of a task by an AI agent. You do not know which model or harness produced it.",
        "Decide whether each numbered condition is satisfied by the evidence. Be strict: a condition passes only if the evidence shows it.",
        'Return only strict JSON: {"verdicts":[{"condition":1,"pass":true,"reason":"..."}]}',
        "", "TASK:", ev["prompt"], "", "EVIDENCE:", evid, "", "CONDITIONS:",
        *[f"{i + 1}. {c}" for i, c in enumerate(exp)],
    ])
    jd = os.path.join(tempfile.gettempdir(), "ethevals-judge"); os.makedirs(jd, exist_ok=True)
    out, err, rc, secs = run_cmd(judge_cmd, prompt, jd, JUDGE_TIMEOUT)
    s, e = out.find("{"), out.rfind("}")
    try:
        verdicts = json.loads(out[s:e + 1])["verdicts"]
        v = {int(x["condition"]): bool(x["pass"]) for x in verdicts}
        res = [v[i + 1] for i in range(len(exp))]
    except Exception as ex:
        return None, [], f"judge output unusable: {ex}; rc={rc} {err[-200:]}"
    reasons = {int(x["condition"]): str(x.get("reason", ""))[:200] for x in verdicts}
    return all(res), res, "; ".join(f"{i + 1}:{'pass' if r else 'FAIL'} {reasons.get(i + 1, '')}" for i, r in enumerate(res))[:600]

# ------------------------------------------------------------------ one eval

def run_one(ev, cmd, judge_cmd, skill_text):
    ws, seed = seed_workspace(ev, skill_text)
    prompt = ev["prompt"]
    reply, err, rc, secs = run_cmd(cmd, prompt, ws, EXEC_TIMEOUT)
    after = snapshot(ws)
    row = {"id": ev["id"], "pillar": ev["pillar"], "kind": ev["kind"], "seconds": round(secs, 1), "rc": rc,
           "reply": reply[-4000:], "files": sorted(k for k in after if seed.get(k) != after[k])}
    if rc == -1:
        row.update(pass_=False, detail=err, dead=True)
    elif "grader" in ev:
        ok, detail = grade_deterministic(ev, reply)
        row.update(pass_=ok, detail=detail)
    else:
        ok, per, detail = judge(ev, evidence(ev, reply, seed, after), judge_cmd)
        row.update(pass_=bool(ok), expects=per, detail=detail, ungraded=(ok is None))
    row["pass"] = row.pop("pass_")
    shutil.rmtree(ws, ignore_errors=True)
    return row

# ------------------------------------------------------------------ self-test

def self_test(evals):
    bad = 0
    for ev in evals:
        if "grader" in ev:
            ok, d = grade_deterministic(ev, ev.get("reference", ""))
            if not ok: bad += 1; print(f"FAIL reference  {ev['id']}: {d}")
            for mp in ev.get("checks", {}).get("must_pass", []):
                ok, d = grade_deterministic(ev, mp)
                if not ok: bad += 1; print(f"FAIL must_pass  {ev['id']}: {mp[:60]!r} {d}")
            for mf in ev.get("checks", {}).get("must_fail", []):
                ok, d = grade_deterministic(ev, mf)
                if ok: bad += 1; print(f"FAIL must_fail  {ev['id']}: {mf[:60]!r} passed")
            for neg in ("Answer: not " + ans_line(ev.get("reference", "")), "The answer is definitely not " + ans_line(ev.get("reference", ""))):
                if not _NEG_RE.search(ev.get("reference", "")):
                    ok, _ = grade_deterministic(ev, neg)
                    if ok: bad += 1; print(f"FAIL negation   {ev['id']}: {neg[:60]!r} passed")
        elif "expect" in ev:
            if not ev["expect"]: bad += 1; print(f"FAIL no expect  {ev['id']}")
        else:
            bad += 1; print(f"FAIL no grader  {ev['id']}")
        if ev.get("workspace") and not os.path.isdir(os.path.join(ev["_dir"], ev["workspace"])):
            bad += 1; print(f"FAIL workspace  {ev['id']}: missing {ev['workspace']}")
    det = sum("grader" in e for e in evals); jud = sum("expect" in e for e in evals)
    print(f"{len(evals)} evals ({det} deterministic, {jud} judged), {bad} problems, manifest {manifest(evals)}")
    return bad == 0

# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true"); ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--name", help="result label, e.g. fable, fable+ethskills")
    ap.add_argument("--executor", choices=sorted(EXECUTORS), help="preset command for a known harness")
    ap.add_argument("--model", help="model id passed to the executor preset")
    ap.add_argument("--cmd", help="custom executor: prompt on stdin, reply on stdout, runs in the workspace")
    ap.add_argument("--harness", help="label for the card (defaults to --executor)")
    ap.add_argument("--skill", help="URL or path of a SKILL.md to install in every workspace")
    ap.add_argument("--judge-cmd", default=JUDGE_DEFAULT)
    ap.add_argument("--pillar", choices=PILLARS); ap.add_argument("--only", nargs="*", help="id substrings")
    ap.add_argument("--limit", type=int); ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--resume", action="store_true", help="skip evals already in results/<name>.json")
    ap.add_argument("--regrade", action="store_true", help="re-grade the deterministic rows of results/<name>.json from their stored replies (no executor runs)")
    a = ap.parse_args()

    evals = load_evals(a.pillar, a.only, a.limit)
    if a.list:
        for e in evals: print(f"{e['id']:44} {e['kind']:5} {'det' if 'grader' in e else 'judge'}  {e['title']}")
        print(len(evals), "evals"); return
    if a.self_test:
        sys.exit(0 if self_test(load_evals()) else 1)
    if not a.name: ap.error("--name is required for a run")
    if a.regrade:
        path = os.path.join(RESULTS_DIR, re.sub(r"[^a-z0-9+._-]", "-", a.name.lower()) + ".json")
        doc = json.load(open(path)); by_id = {e["id"]: e for e in load_evals()}; flips = 0
        for r in doc["rows"]:
            ev = by_id.get(r["id"])
            if not ev or "grader" not in ev or r.get("dead"): continue
            ok, detail = grade_deterministic(ev, r["reply"])
            if ok != r["pass"]: flips += 1; print(f"  {r['id']}: {r['pass']} -> {ok}  {detail[:80]}")
            r["pass"], r["detail"] = ok, detail
        for p in PILLARS:
            rs = [r for r in doc["rows"] if r["pillar"] == p]
            doc["pillars"][p] = {"pass": sum(r["pass"] for r in rs), "total": sum(1 for e in by_id.values() if e["pillar"] == p)}
        doc["total"] = {"pass": sum(v["pass"] for v in doc["pillars"].values()), "total": sum(v["total"] for v in doc["pillars"].values())}
        doc["manifest"] = manifest(load_evals())
        json.dump(doc, open(path, "w"), indent=1)
        print(f"{a.name}: regraded, {flips} verdicts changed, now {doc['total']['pass']}/{doc['total']['total']}"); return
    cmd = a.cmd or (EXECUTORS[a.executor](a.model) if a.executor and a.model else None)
    if not cmd: ap.error("give --executor and --model, or --cmd")
    if not self_test(load_evals()): sys.exit("self-test failed; fix the evals before running")

    skill_text = None
    if a.skill:
        skill_text = urllib.request.urlopen(a.skill, timeout=30).read().decode() if a.skill.startswith("http") else open(a.skill).read()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, re.sub(r"[^a-z0-9+._-]", "-", a.name.lower()) + ".json")
    prev = json.load(open(out_path)) if a.resume and os.path.exists(out_path) else None
    rows = {r["id"]: r for r in (prev or {}).get("rows", [])}
    todo = [e for e in evals if e["id"] not in rows]
    print(f"{a.name}: {len(todo)} evals to run, {len(rows)} kept, concurrency {a.concurrency}\n  executor: {cmd}\n  judge:    {a.judge_cmd}")

    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    def save():
        by = {}
        for p in PILLARS:
            rs = [r for r in rows.values() if r["pillar"] == p]
            by[p] = {"pass": sum(r["pass"] for r in rs), "total": sum(1 for e in load_evals(p))}
        doc = {"name": a.name, "model": a.model or a.name, "harness": a.harness or a.executor or "custom", "skill": a.skill,
               "executor_cmd": cmd, "judge_cmd": a.judge_cmd, "started": started, "manifest": manifest(load_evals()),
               "pillars": by, "total": {"pass": sum(v["pass"] for v in by.values()), "total": sum(v["total"] for v in by.values())},
               "rows": sorted(rows.values(), key=lambda r: r["id"])}
        json.dump(doc, open(out_path, "w"), indent=1)
    save()
    with cf.ThreadPoolExecutor(max_workers=a.concurrency) as pool:
        futs = {pool.submit(run_one, e, cmd, a.judge_cmd, skill_text): e for e in todo}
        for f in cf.as_completed(futs):
            r = f.result(); rows[r["id"]] = r; save()
            flag = "PASS" if r["pass"] else ("DEAD" if r.get("dead") else ("????" if r.get("ungraded") else "fail"))
            print(f"  {flag}  {r['id']:44} {r['seconds']:6.0f}s  {r.get('detail', '')[:100]}")
    doc = json.load(open(out_path))
    print(f"\n{a.name}: {doc['total']['pass']}/{doc['total']['total']}  " + "  ".join(f"{p} {v['pass']}/{v['total']}" for p, v in doc["pillars"].items()))
    print(f"wrote {os.path.relpath(out_path, ROOT)}; run `python3 build.py` to refresh the site index")

if __name__ == "__main__":
    main()
