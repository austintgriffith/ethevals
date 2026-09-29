# ethevals, multiple choice

The main suite needs written answers. Decision models (TypeSafe Jev, Levanto Sage)
can only pick from options, so this is a 4-option version they can take.

- `questions.json`: 99 questions, one per eval (`transactions-19` was dropped, see `dropped.json`).
- `tools/gen_mc.py` made them. Opus writes each question from its eval, with wrong
  options taken from the mistake the eval targets. Then either the eval's own grader
  checks it (33) or a blind Fable pass does (66). A last pass rewrites options so the
  right one isn't the longest.
- `run_mc.py` runs it. `results/` has one file per run.

```
python3 run_mc.py --name jev-1.13 --backend jev          # TYPESAFE_API_KEY in .env
python3 run_mc.py --name sage-1.2 --backend sage         # SAGE_API_KEY in .env
python3 run_mc.py --name claude-haiku --backend claude --model haiku
python3 run_mc.py --report
```

## First run (2026-09-29)

| model | right | top pick | no answer | median time |
|---|---|---|---|---|
| Claude Opus 5.5 | 99% | | 1 | 3.0 s |
| Claude Sonnet 5 | 92% | | 0 | 2.4 s |
| Claude Haiku 4.5 | 85% | | 4 | 9.8 s |
| Jev 1.13 | 83% | 83% | 0 | 0.19 s |
| Sage 1.2 | 59% | 65% | 20 | 0.8 s |
| Sage 1.2, reasoning on | 22% | 36% | 42 | 5.2 s |

"Top pick" counts Sage's highest-probability option even when it said "too close to call".

Caveats:
- Opus wrote the questions and Fable checked them, so both Claude scores at the top are likely inflated.
- Multiple choice is much easier than the main suite: Haiku scores 47 there and 85 here.
- Jev and Sage were sent the question and options with no prompt tuning.
