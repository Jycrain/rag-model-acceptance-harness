# Methodology: comparing LLMs behind any LLM-backed system

The end-to-end method that the code in this repo implements. It was distilled from a real acceptance campaign and rewritten so that nothing in it depends on that engagement.
It applies whenever you must answer "which model / prompt / configuration should this system use?" with evidence rather than impressions.

## 0. Principles

1. **Measure through the real path.** Every answer is obtained through the application's own back end, with the credentials of the
   system under test. A model provider's key bypasses retrieval, prompts and guard-rails: results obtained that way are not
   results of the application and must never be mixed in. (Direct provider calls are acceptable only as throw-away diagnostics.)
2. **One question set, frozen.** The set is fingerprinted (SHA-256 of `id<TAB>question` lines). Every series records the
   fingerprint; the comparison refuses to run if two series disagree. "Identical protocol" means same questions, same order,
   same one-message conversation, not identical answers. Changing the set starts a new, non-comparable series.
3. **Scripts collect, LLMs do not.** Collection is deterministic code (0 LLM agents), cheap to repeat and easy to audit.
   LLMs are used only after collection, for blind audits of the statuses.
4. **One status rule, no exceptions.** See [status-rule.md](status-rule.md).
5. **Numbers come from journals only.** Every figure in a workbook or a deck is computed from the `.jsonl` journals by one
   script and stored in a stats file; slides and sheets read that file, nobody types a number.
6. **A discriminating probe before any series.** See [data-collection.md](data-collection.md).
7. **Independent verification before delivery.** See [quality-guards.md](quality-guards.md).

## 1. Stages of a campaign

| Stage | What happens | Lesson kept |
|---|---|---|
| Framing | The owner validates the recurring questions; profiles (user types) and models are fixed; deliverable wording agreed (factual restitution: no names, no internal matters, no blame). | Write the restitution rules down first: they constrain every later artefact. |
| Pilot through the front end (optional) | Replays through the UI. | A front-end replay hides which tenant or session answered: verify it line by line, or go straight to the API. |
| Series through the API | Same questions through the back end's API. Faster, no UI dependency, structured journals. | Move to the API as soon as the route is known; keep the front end only for UI questions. |
| Repeated series | Models or prompts change, labels move. | Re-probe labels before every series; record the requested label on every line. |
| Status incident (it happens) | A hand-made exception ranks a sourceless answer Ok. | See [lessons-learned.md](lessons-learned.md): rule governance, blocking tests, blind audit. |
| Parallel series | Several configurations replayed at once. | Parallel runs make timings meaningless: drop timing columns until re-measured cleanly. |
| Cost estimate | Usage is often not returned, so cost is a range built from logged volumes and explicit assumptions. | See [cost-estimation.md](cost-estimation.md). |

## 2. Run protocol

1. **Probe the label** (`src/probe_model_label.js`) for each model. Include an unknown control label that must fail: without it the probe proves nothing.
2. **Pre-flight**: one request per (profile, model) with the final label, before the full series.
3. **Collect** (`src/run_api.js`, any [adapter](adapters.md)): one call per question per profile, pause, timeout, 1 retry, stop after 3
   consecutive failures. Resume skips ids already logged `ok`. Keys never reach the logs.
4. **Compare** (`src/compare.py`): blocking controls, writes the stats file.
5. **Build** (`src/build_excel.py`, `src/build_deck.js`): summary + one detail sheet per series.
6. **Verify** (`src/verify_deliverables.py`) and **audit** (`src/audit_prepare.py` / `audit_consensus.py`, [skill](../compound/skills/blind-audit/SKILL.md) or [prompts](../prompts/README.md)).
7. **Estimate cost** (`src/cost_estimate.py`) if asked.

## 3. Reporting rules that mattered

- Orange is a real status ("Ok - partial"), between Ok and Ko, so the reader sees answers that exist but cite nothing.
- Say what the status measures: **presence of a cited source, not the relevance of the answer.** A relevance score needs a
  human (or a rubric-based LLM judge) and is never claimed here.
- Deliver only what the current priority needs. If the owner's priority is answer shape and sources, remove noisy timing columns (with a note) rather than shipping them.
- Give column legends on the slide that shows the table. A matrix of numbers without a legend is read wrongly.
- Client-facing material: no participant names, no internal budget/team/tension remarks, no blame.
