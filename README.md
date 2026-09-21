# ethevals

How much does your AI actually know about Ethereum?

A benchmark and a results site. Models, agents, skills and harnesses are scored on
four pillars: **concepts**, **transactions**, **building**, **security**. Twenty-five
evals per pillar, each keyed to a mistake seen in real agent output.

- `index.html` — the site. One file, no build; it reads `evals/index.json` and `results/index.json`.
- `evals/<pillar>/*.yaml` — the 100 evals. `kind: quiz` is a written answer, `kind: goal` is a build task judged on files.
- `run.py` — runs the suite against any executor and grades it. `python3 run.py --help`.
- `build.py` — regenerates the two index files after adding an eval or a result.
- `RUN.md` — what an agent reads to score itself and submit a result.
- `results/*.json` — one file per run: model, harness, skill, executor and judge commands, per-eval rows.

## Run it

```
python3 -m pip install pyyaml
python3 run.py --self-test
python3 run.py --name fable-5.1 --executor claude --model fable
python3 run.py --name fable-5.1+ethskills --executor claude --model fable --skill https://ethskills.com/SKILL.md
python3 build.py
```

Any command that takes the prompt on stdin and prints the reply works as an executor
(`--cmd`). Half the evals have deterministic graders; the other half are graded by a
blind LLM judge (`--judge-cmd`, default `claude -p --model sonnet`).

## Where the evals come from

- [BuidlGuidl/ethskills-evals](https://github.com/BuidlGuidl/ethskills-evals) — goal and quiz tasks with judged expect lines; `tools/port_sources.py` copies them with their rubrics intact.
- [clawdbotatg/eth-evals](https://github.com/clawdbotatg/eth-evals) — closed-book tasks with deterministic graders and adversarial fixtures.
- `tools/gen_authored.py` — evals written here; calldata answers are computed with foundry's `cast`.

Both port scripts are the source of truth for the evals they generate. Edit the script and re-run it.

## Site

```
python3 -m http.server 8000   # then open http://localhost:8000
```

Design follows [ethskills.com](https://ethskills.com), in Ether blue.
