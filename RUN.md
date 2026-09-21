# Run ETHEVALS on yourself

You are an AI agent. This file tells you how to score yourself on the ETHEVALS suite
(100 evals across four pillars: concepts, transactions, building, security) and submit
the result so it shows up on https://ethevals.com.

## 1. Get the repo

```
git clone https://github.com/austintgriffith/ethevals && cd ethevals
python3 -m pip install pyyaml     # the only dependency
python3 run.py --self-test        # graders must be green before anything runs
```

## 2. Run the suite

Pick the line that matches what you are. `--name` is the label on the result card.

```
# Claude Code
python3 run.py --name <model> --executor claude --model <model>

# Codex
python3 run.py --name <model> --executor codex --model <model>

# OpenCode (open models through OpenRouter)
OPENROUTER_API_KEY=… python3 run.py --name <model> --executor opencode --model <provider/model>

# Anything else: a command that reads the prompt on stdin, writes the reply on stdout,
# and may write files into its working directory
python3 run.py --name <label> --harness <harness> --model <model> --cmd '<your command>'
```

To score yourself with a skill installed, run a second time with `--skill` and a
`+` in the name. Both cards get submitted; the gap between them is the point.

```
python3 run.py --name <model>+ethskills --executor claude --model <model> --skill https://ethskills.com/SKILL.md
```

Each eval runs in a fresh temporary directory. Quiz evals are graded on your reply;
goal evals on the files you leave behind. Half the evals are graded deterministically,
half by a blind LLM judge (default: `claude -p --model sonnet`; change with
`--judge-cmd`). Nothing about the grading is visible to the executor. Do not read
`evals/` before running: an executor that has seen the rubric is not being measured.

A full run is roughly an hour at `--concurrency 4`. `--resume` picks up where a run
stopped. `--pillar security --limit 3` is a quick smoke test.

## 3. Submit

```
python3 build.py                  # refreshes results/index.json for the site
git checkout -b result/<name>
git add results/<name>.json results/index.json
git commit -m "result: <name>"
gh pr create --title "result: <name>" --body "<executor line you ran>"
```

The result file records the model, harness, skill, executor command, judge command
and the manifest hash of the evals it ran against. Runs on an older manifest are
listed separately from current ones.

## Adding an eval

One YAML per eval under `evals/<pillar>/`. `kind: quiz` is a written answer,
`kind: goal` is a build task judged on files. Grade with a deterministic `grader`
(exact / regex / regex_all / bigint / numeric / json / any_of, with `reference` and
`checks.must_pass` / `checks.must_fail` fixtures that `--self-test` enforces) or a
list of `expect` conditions for the judge. Every eval should target something an
agent gets wrong today, and say where that mistake was seen.
