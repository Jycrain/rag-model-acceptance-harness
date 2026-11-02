---
name: rag-model-acceptance
description: Run a reproducible acceptance campaign that compares several LLMs behind a RAG back end (collect through the API, rank answers with one status rule, audit blind, build workbook/deck, estimate cost) and keep the client context anonymised. Use when asked to compare models on a RAG assistant, to replay a question set against agents, to estimate the cost of such runs, or to turn client work into a public, anonymised repo.
---

# RAG model acceptance campaign

Reusable procedure distilled from a real campaign. The code lives in the repo that ships this skill (`src/`, `tests/`, `docs/`).
Follow the phases in order; each ends with a gate. Never skip a gate to save time.

## Phase 0: frame (ask the owner BEFORE any call to the back end)

Ask, and write the answers in a note, one question at a time if the owner prefers:
1. Which agents/profiles, which models, which exact labels (to be probed, not guessed)?
2. Which question set, who validated it, is it frozen? (fingerprint it)
3. What is the status rule? Default: Ok = complete answer with ≥ 1 cited source; Ok - partial = no source; Ko = failure/empty/truncated.
   **Any other rule needs a written criterion validated by the owner.**
4. What is the priority now (answer shape and sources, speed, cost)? Drop the metrics that are not the priority.
5. Restitution rules for the client (no names, no internal matters, no blame)?
6. Token budget: scripts collect, LLM agents only audit.
7. Is the key of the *agent* available for every profile? (Never use a provider key for results.)

Gate: owner confirmation of scope, labels to probe, status rule.

## Phase 1: probe

Pick the adapter (`api.type`: `openai_chat_sse`, `json_http` or `command`, see `docs/adapters.md`) and the citation preset (`citation.preset`) first. Then `node src/probe_model_label.js` with candidate labels + an unknown control (must be rejected). Then `node src/probe_usage.js`
to learn whether tokens are returned. Report missing labels; never substitute silently. Gate: one accepted label per model, recorded.

## Phase 2: pre-flight and collect

One request per (profile, model), then `node src/run_api.js` per model (parallel is fine for answers, not for timings).
Never print or log a key. Resume skips `ok` ids. Gate: every series has exactly one `ok` pass per (profile, question).

## Phase 3: compare

`python src/compare.py --config <cfg>`; all controls must be green. A conflict from the broad detector blocks: ask the owner, record the
decision in `validated_conflicts.json` (never change `status.py` for it).

## Phase 4: audit (sub-agents, blind)

Use the `blind-audit` skill (light or full mode; agents `blind-reviewer` and `adversary`; workflow `blind-audit.workflow.js`).
`audit_prepare.py` → reviewers get batches, never `key.json` → `audit_consensus.py --pack --objections`. Missed canary, non-literal quote or objection = stop;
arbitrate with the owner. Write the audit report the same day with coverage and limits.

## Phase 5: deliver

`python src/build_excel.py`, `python src/verify_deliverables.py`, build the deck from the stats file only, reopen files in the real
application. Legends must say "presence of a cited source, not relevance".

## Phase 6: cost (if asked)

Follow `docs/cost-estimation.md`. Prefer measured tokens (platform logs / provider console) to assumptions; show low/central/high;
cite price sources and dates; models only.

## Phase 7: generalise and anonymise (if the repo goes public)

Follow `docs/anonymization.md`: new history, synthetic demo data, real-term list kept OUTSIDE the repo
(`HARNESS_FORBIDDEN_FILE`), generic scan + private scan + blind read, written authorisation, private first.

## Rules that always apply

- Stop and ask when a decision belongs to the owner; bring one concrete recommendation.
- A status describes a draw, not the model: do not over-read differences of one or two passes.
- Numbers come from journals via one script; nobody types a figure.
- Report outcomes faithfully: say what was not verified (routing, relevance, citation correctness).

## Install

Copy this folder to `~/.claude/skills/rag-model-acceptance/` (or reference it from a plugin). The skill expects the repo's `src/` next to it.
