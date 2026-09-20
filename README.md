# ethevals

How much does your AI actually know about Ethereum?

A static site plus an eval suite that scores LLMs, agents, skills and harnesses on
four pillars of Ethereum knowledge: **concepts**, **transactions**, **building**, **security**.
Twenty evals per pillar, each keyed to a mistake seen in real agent output.

- `index.html` — the site. One file, no build. Design follows [ethskills.com](https://ethskills.com) in Ether blue.
- Results cards on the front page are placeholders until real runs are recorded.

Sources the evals are drawn from:

- [BuidlGuidl/ethskills-evals](https://github.com/BuidlGuidl/ethskills-evals) — goal/quiz tasks, blind LLM judge
- [clawdbotatg/eth-evals](https://github.com/clawdbotatg/eth-evals) — closed-book tasks, deterministic graders

## Run locally

```
python3 -m http.server 8000
```

Then open http://localhost:8000.
