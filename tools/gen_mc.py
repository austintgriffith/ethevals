#!/usr/bin/env python3
"""Turn the 100 evals into 4-option multiple-choice questions: mc/questions.json.

Decision models (TypeSafe Jev, Levanto Sage) can't write text, so they can't take the
main suite. This makes a version they can take.

  python3 tools/gen_mc.py                 # every eval not already in mc/questions.json
  python3 tools/gen_mc.py --only security-01 --redo

One writer call per eval (Opus by default) drafts the stem, the right answer and three
wrong answers built from the mistake the eval targets. Then:
  - evals with a deterministic grader: the grader must pass the right answer and fail
    every wrong one (checked in code, no model involved);
  - judged evals: a second, blind call checks that exactly one option is right and that
    it is the keyed one.
Anything that fails is dropped, with the reason, into mc/dropped.json.
Answer letters are shuffled in code so the right answer isn't always A.
"""
import argparse, concurrent.futures as cf, hashlib, json, os, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import run  # noqa: E402

OUT = os.path.join(ROOT, "mc", "questions.json")
DROPPED = os.path.join(ROOT, "mc", "dropped.json")
LETTERS = "ABCD"

WRITE = """You are turning one Ethereum eval into a fair 4-option multiple-choice question.

The eval below was written for an AI that answers in free text. Rewrite it so the
answer is one pick from four options. Rules:

- The stem must stand alone. Keep every fact needed to answer (code, numbers,
  addresses). Drop output instructions ("write answer.md", "Answer: ...").
- If the eval asks for several things, test the one insight it is really about
  (the mistake it targets). One question, one right answer.
- Exactly one option is right. Copy it from the reference when there is one
  (hex strings and numbers verbatim).
- The three wrong options must be plausible: the mistakes an AI would actually
  make here. At least one must be the exact mistake the eval was written to catch.
  They must be clearly wrong to an expert, not matters of taste.
- If the eval is already multiple choice, keep its right option's text and its
  three most tempting wrong options (write them out; no letters in the options).
- Options are plain answers: no "Answer:" prefix, no letter labels.
- Keep all four options similar in length and style. Don't make the right one the
  longest or the most hedged.
- If the eval cannot be made into a fair single-answer question, set "skip" to a
  one-line reason and leave the rest empty.

Reply with only a JSON object, no code fence:
{"stem": "...", "right": "...", "wrong": ["...", "...", "..."], "mistake": "which wrong option is the targeted mistake, in a few words", "skip": null}

THE EVAL
"""

CHECK = """Here is a multiple-choice question about Ethereum. Answer it as an expert, then
judge the question itself.

Reply with only a JSON object, no code fence:
{"answer": "<letter>", "only_one_right": true|false, "problem": "<empty, or one line on what is wrong with the question>"}

"only_one_right" is false if more than one option is defensible or none is right.

"""


def eval_text(ev):
    keep = {k: ev[k] for k in ("title", "summary", "prompt", "reference", "expect", "source_quote") if ev.get(k)}
    if ev.get("grader"):
        keep["grader"] = ev["grader"]
    return json.dumps(keep, indent=1, ensure_ascii=False)


def claude(prompt, model):
    out, err, rc, _ = run.run_cmd(f"claude -p --model {model} --strict-mcp-config --disallowedTools Bash,Edit,Write,WebFetch,WebSearch",
                                  prompt, ROOT, 600)
    if rc != 0:
        raise RuntimeError(f"claude rc={rc}: {(err or out)[:200]}")
    m = re.search(r"\{.*\}", out, re.S)
    if not m:
        raise RuntimeError(f"no JSON in reply: {out[:200]}")
    return json.loads(m.group(0))


BALANCE = """This multiple-choice question has a flaw: the right option is the longest, so
a test-taker can guess it from length alone. Fix that without changing which option is
right or what any option means:
- make at least two wrong options as long as the right one or longer, with plausible,
  specific (still wrong) detail, and/or trim filler from the right option;
- keep hex strings, numbers and code exact; keep the stem unchanged.

Reply with only a JSON object, no code fence, holding all four options by letter:
{"A": "...", "B": "...", "C": "...", "D": "..."}

The right option is %s.

"""


def longest(q):
    return max(q["options"], key=lambda L: len(q["options"][L]))


def balance(q, ev, writer, checker):
    """Rewrite options so the right one isn't the longest, then re-verify."""
    if longest(q) != q["answer"] or all(v.startswith("0x") for v in q["options"].values()):
        return q, None
    try:
        new = claude(BALANCE % q["answer"] + render(q), writer)
        fixed, _ = verify({**q, "options": {L: new[L].strip() for L in LETTERS}}, ev, checker)
    except Exception:
        fixed = None
    return (fixed or q), None  # a rewrite that fails verification keeps the original


def render(q):
    return q["stem"] + "\n\n" + "\n".join(f"{L}) {q['options'][L]}" for L in LETTERS)


def make(ev, writer, checker):
    d = claude(WRITE + eval_text(ev), writer)
    if d.get("skip"):
        return None, f"writer skipped: {d['skip']}"
    wrong = [w for w in d.get("wrong", []) if w and w.strip() != d["right"].strip()]
    if len(wrong) != 3:
        return None, "writer did not give three distinct wrong options"
    opts = [d["right"]] + wrong
    rng = random.Random(int(hashlib.sha256(ev["id"].encode()).hexdigest(), 16))
    order = list(range(4))
    rng.shuffle(order)
    options = {LETTERS[i]: opts[j] for i, j in enumerate(order)}
    answer = LETTERS[order.index(0)]
    q = {"id": ev["id"], "pillar": ev["pillar"], "title": ev["title"], "stem": d["stem"].strip(),
         "options": options, "answer": answer, "mistake": d.get("mistake", "")}
    q, why = verify(q, ev, checker)
    if not q:
        return None, why
    return balance(q, ev, writer, checker)


def verify(q, ev, checker):
    options, answer = q["options"], q["answer"]
    how = "checker"
    letter_key = re.match(r"^Answer:\s*\(?[A-H]\)?\s*$", str(ev.get("reference", "")))
    if ev.get("grader") and not letter_key:
        # Many graders only read a letter or a JSON blob from the original prompt's own
        # format, so they can't grade option text. A grader that passes a wrong option
        # still disqualifies the question; one that can't read the right one hands off
        # to the checker.
        for L, text in options.items():
            ok, detail = run.grade_deterministic(ev, f"Answer: {text}")
            if ok and L != answer:
                return None, f"grader passed wrong option {L}: {detail}"
        if run.grade_deterministic(ev, f"Answer: {options[answer]}")[0]:
            how = "grader"
    if how == "checker":
        c = claude(CHECK + render(q), checker)
        if not c.get("only_one_right"):
            return None, f"checker: not exactly one right option: {c.get('problem', '')}"
        if str(c.get("answer", "")).strip().upper()[:1] != answer:
            return None, f"checker picked {c.get('answer')} not {answer}: {c.get('problem', '')}"
    q["verified_by"] = how
    return q, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--redo", action="store_true", help="regenerate ids already in the file")
    ap.add_argument("--balance", action="store_true", help="only re-run the length-balance pass on existing questions")
    ap.add_argument("--writer", default="opus")
    ap.add_argument("--checker", default="fable")
    ap.add_argument("--concurrency", type=int, default=6)
    a = ap.parse_args()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    have = {q["id"]: q for q in json.load(open(OUT))} if os.path.exists(OUT) else {}
    dropped = json.load(open(DROPPED)) if os.path.exists(DROPPED) else {}
    evals = run.load_evals(only=a.only)
    todo = [e for e in evals if a.redo or e["id"] not in have]
    job = lambda e: make(e, a.writer, a.checker)
    if a.balance:
        todo = [e for e in evals if e["id"] in have]
        job = lambda e: balance(have[e["id"]], e, a.writer, a.checker)
    print(f"{len(todo)} evals to convert", file=sys.stderr)

    def save():
        order = {e["id"]: i for i, e in enumerate(run.load_evals())}
        json.dump(sorted(have.values(), key=lambda q: order.get(q["id"], 1e9)), open(OUT, "w"), indent=1, ensure_ascii=False)
        json.dump(dict(sorted(dropped.items())), open(DROPPED, "w"), indent=1, ensure_ascii=False)

    with cf.ThreadPoolExecutor(a.concurrency) as pool:
        futs = {pool.submit(job, e): e for e in todo}
        for f in cf.as_completed(futs):
            ev = futs[f]
            try:
                q, why = f.result()
            except Exception as e:
                q, why = None, f"error: {e}"
            if q:
                have[ev["id"]] = q
                dropped.pop(ev["id"], None)
                print(f"ok    {ev['id']}", file=sys.stderr)
            else:
                have.pop(ev["id"], None)
                dropped[ev["id"]] = why
                print(f"drop  {ev['id']}: {why}", file=sys.stderr)
            save()
    print(f"{len(have)} questions, {len(dropped)} dropped", file=sys.stderr)


if __name__ == "__main__":
    main()
