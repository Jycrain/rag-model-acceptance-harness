---
name: blind-audit
description: Audit the statuses of a model-comparison campaign with blind LLM reviewers, canaries and an adversary. Use after compare.py is green, before delivering, or when a status rule has just changed.
---

# Blind audit

Two modes. Pick by stakes; write the mode and its limits in the deliverable.

| Mode | When | Design | Agents |
|---|---|---|---|
| Light | internal check, no decision rides on it | one reviewer, all partials + stratified greens (≥ 5 per cell), 2 canaries, fixed seed | 1 to 2 |
| Full | the comparison backs a decision | 3 reviewers of different model tiers × batches of ~22 cases with ≥ 3 canaries each, then 1 adversary per batch, literal-quote check, consensus | ≤ 10 per run; more = ask |

## Procedure
1. `python src/audit_prepare.py --config <cfg> --per-cell 5 --seed <n> --batch-size 22 --out audit/`. Set a plausible `canary_marker` in the config (a fake-looking one gets spotted by the adversary and proves little). Keep `audit/` out of git. Record seed and sizes: batch files are NOT reproducible from memory, the seed and config are.
2. Give reviewers `audit/batches/batch-NN.json` only. Never `key.json`. Light mode: spawn `blind-reviewer` yourself. Full mode: run `compound/workflows/blind-audit.workflow.js` with the batches as `args`.
3. Write each reviewer's JSON to `audit/reviewer-<k>.json` and the adversary's objections to `audit/objections.json`.
4. `python src/audit_consensus.py audit/key.json audit/reviewer-*.json --pack audit/pack.json --objections audit/objections.json`.
   Exit 1 = canary missed (void, rerun that batch), non-literal quote (reviewer did not read), or objection (arbitrate).
5. Disagreement or objection: the owner decides; the decision is a dated note or a `validated_conflicts.json` entry bound to the answer hash. Never edit `status.py` for one case.
6. Write `audit/REPORT.md` the same day: mode, seeds, sizes, coverage (n audited / n per status), agreement, disagreements and decisions, limits. A report written later is a reconstruction.

## Limits to state every time
Coverage per cell (5 greens of ~36 cannot detect an error rate of 10 to 15 %); relevance of sources not scored; reviewers are LLMs; canaries can be recognised.
