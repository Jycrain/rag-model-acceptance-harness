# LLM acceptance harness

A reproducible, platform-agnostic way to **compare language models (or prompts, or configurations) behind any LLM-backed system**:
a RAG assistant, an agent, a chat endpoint, a CLI. Replay a frozen question set, rank every answer with **one rule without
exceptions**, audit it blind with independent reviewers, produce a workbook and a deck, and estimate what the runs cost.

It started as the tooling of a real acceptance campaign and was generalised: nothing in the code, the docs or the demo data
depends on that engagement ([anonymization.md](docs/anonymization.md) explains what that does and does not guarantee).

```
questions.json ──► run_api.js ──► runs/<series>/<profile>.jsonl ──► compare.py ──► stats.json
 (frozen, SHA-256)   (any back end      (one JSON line per pass)       (blocking controls)   │
                      via an adapter)                                                         ├─► build_excel.py ─► verify_deliverables.py
                                                                                              ├─► build_deck.js
        status.py (single rule) ◄── imported by everything ──                                 ├─► audit_prepare.py ─► blind reviewers ─► audit_consensus.py
                                                                                              └─► cost_estimate.py
```

## What is agnostic, and how

| Axis | How it is configured | Where |
|---|---|---|
| **Back end** | `api.type`: `openai_chat_sse` (any OpenAI-compatible endpoint), `json_http` (any JSON API: body template + answer path), `command` (any CLI or script: question on stdin, answer on stdout) | [docs/adapters.md](docs/adapters.md), `src/adapters.js` |
| **Citation format** | `citation.preset`: `bracket_id`, `bracket_number`, `markdown_link`, `bold_prefixed`, `custom` | `src/config.py`, [docs/status-rule.md](docs/status-rule.md) |
| **What is compared** | models, prompt variants, retrieval settings: anything you can name as a "series" with a label | `models` + `series` in the config |
| **Who audits** | Claude Code (skills, agents, workflow), or **any** LLM / human reader through plain-markdown prompts and the same scripts | [AGENTS.md](AGENTS.md), `prompts/`, `compound/` |
| **Language and domain** | questions and answers are opaque text; the demo is a fictional library | `examples/demo/` |

## Quick start (demo, no network, no secrets)

```bash
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
python examples/demo/generate_demo.py                                   # synthetic library-assistant data
python tests/test_status.py && python tests/test_audit.py && python tests/test_no_leak.py && python tests/test_collect_e2e.py
node tests/test_adapters.js                                             # the three adapters against a local mock server
python src/compare.py --config examples/demo/config.json                # blocking controls
python src/build_excel.py --config examples/demo/config.json --out comparison.xlsx
python src/verify_deliverables.py --config examples/demo/config.json comparison.xlsx
python src/cost_estimate.py --config examples/demo/config.json          # low / central / high (placeholder prices)
```

## Use it on a real system

1. Copy `config.example.json` → `config.json`, `.env.example` → `.env` (git-ignored). Pick `api.type` and `citation.preset`.
   Write `questions.json` (`[{"id":"01","n":1,"theme":"…","q":"…"}]`) and freeze it (its SHA-256 is recorded in every series).
2. `node src/probe_model_label.js --config config.json --profile profile_a <label…>`: an unknown control label must fail.
3. `node src/run_api.js --config config.json --profile profile_a --model model-1` (per profile, per model; resumable).
4. `compare.py` → `build_excel.py` → `verify_deliverables.py`.
5. Audit: `audit_prepare.py` → blind reviewers → `audit_consensus.py` ([skill `blind-audit`](compound/skills/blind-audit/SKILL.md) or [prompts/](prompts/README.md)).

## The ideas worth stealing

- **One status rule, no exceptions** (Ok / Ok - partial / Ko), governed in writing: [docs/status-rule.md](docs/status-rule.md)
- **Blocking quality guards**, blind stratified audit with canaries, literal quotes and an adversary: [docs/quality-guards.md](docs/quality-guards.md)
- **A discriminating probe** for model labels, and what an API cannot tell you: [docs/data-collection.md](docs/data-collection.md)
- **Cost as a range with explicit assumptions**: [docs/cost-estimation.md](docs/cost-estimation.md)
- **Mistakes made and what now prevents them**: [docs/lessons-learned.md](docs/lessons-learned.md) · **experience report**: [docs/rex.md](docs/rex.md)
- **The whole method**: [docs/methodology.md](docs/methodology.md) · **worked example on synthetic data**: [docs/worked-example.md](docs/worked-example.md)
- **Anonymising client work before publishing**: [docs/anonymization.md](docs/anonymization.md)
- **Agent tooling** (skills, agents, workflow, portable prompts): [compound/README.md](compound/README.md), [AGENTS.md](AGENTS.md)

## Limits

- Routing to the requested model is not verifiable from most APIs (only label acceptance is).
- The status measures the presence of a cited source, not relevance or correctness. Audits do not cover that either.
- Timings from parallel runs are not clean measurements.
- Cost figures are estimates unless you feed measured token totals.
- LLM reviewers can be wrong or recognise canaries; state the audit mode and coverage with every result.

## Layout

`src/` pipeline · `tests/` guards · `examples/demo/` synthetic data · `docs/` method · `prompts/` portable reviewer prompts · `compound/` Claude Code tooling + leak scanner · `.github/workflows/ci.yml`.

MIT licence.
