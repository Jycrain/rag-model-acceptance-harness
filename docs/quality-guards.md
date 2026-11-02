# Quality guards

Seven layers, from cheapest to most expensive. Each one exists because the layer before it missed something.

| # | Guard | Where | Catches |
|---|---|---|---|
| 1 | Unit tests with golden cases | `tests/test_status.py` | rule drift, return of an exception |
| 2 | Journal invariants | `tests/test_status.py::DemoData`, `src/compare.py` | missing/extra passes, mixed labels, truncated streams, empty answers |
| 3 | Two counting methods for sources | `src/compare.py` | a regex that silently changes what a "source" is |
| 4 | Broad detector + signed decisions | `src/status.py::conflict`, `src/conflicts.py` | answers that look sourced but are ranked partial (bare URLs) |
| 5 | Independent re-read of the workbook | `src/verify_deliverables.py` | build bugs, copy errors, stale sheets |
| 6 | Blind stratified audit with canaries | `src/audit_prepare.py`, `src/audit_consensus.py` | rule gaps that code cannot see (announcement answers) |
| 7 | Fingerprints | question set SHA-256, journal SHA-256 in the stats file | silent changes of inputs between build and delivery |

## Blocking, not advisory

`compare.py` exits 1 on any mismatch; `build_excel.py` refuses to write if the status tests fail; a deck builder reads only
the stats file and its own assertions. A guard that only prints a warning is not a guard.

## The blind stratified audit

1. **Stratify.** For every (series, profile) cell take *all* partial answers and N random Ok answers (fixed seed).
   A simple random draw over all green answers can leave a whole cell unchecked (it happened: see lessons).
2. **Blind.** Reviewers (LLM sub-agents or humans) get the question, the answer, and the citation convention. They never see the
   pipeline status. Ask two questions per case: "is a source cited?" and "is the answer complete?".
3. **Canaries.** Add two per run: an Ok answer with its markers stripped (must be judged sourceless) and a partial answer with a
   fake marker injected (must be judged sourced). A missed canary voids the audit.
4. **Consensus.** `audit_consensus.py` compares reviewer majority with the pipeline; disagreements go to the owner.
5. **What it cannot do.** The audit checks the *rule application* and the plausibility of completeness. It does not verify that
   a cited document really supports the claim; unless you run the literal-quote check (`audit_consensus.py --pack`), citations are not checked against the claims. Say so.

## Delivery checklist

- [ ] `python tests/test_status.py` green
- [ ] `python src/compare.py` all controls green; fingerprints identical across series
- [ ] workbook opened and re-read by `verify_deliverables.py` (all cells consistent)
- [ ] workbook/deck reopened by name in the real application (a file can build and still not open)
- [ ] audit sample drawn with the documented seed; canaries caught
- [ ] legends say "presence of a cited source, not relevance"
- [ ] client-facing text reviewed against the restitution rules (no names, no internal matters, no blame)
- [ ] leak scan (generic + private list) clean before anything leaves the machine


## Audit coverage and detection power
State coverage with every audit result: partials audited / total, greens audited / total, per (series, profile) cell. With 5 greens drawn from about 36 per cell,
an error rate of 10 to 15 % in a cell can pass unnoticed. `audit_consensus.py` exits 1 on a missed canary, on a quote that is not a literal substring of the answer
(`--pack`), and on any adversary objection (`--objections`); `audit_prepare.py --batch-size` writes batches for the full multi-reviewer design
(see `compound/skills/blind-audit/SKILL.md`).
