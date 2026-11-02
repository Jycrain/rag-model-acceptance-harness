# Experience report: an intensive acceptance campaign

What worked, what did not, and what is still unproven, from an acceptance campaign that compared language models behind a real RAG assistant.
Written after the fact from the project files; every figure comes from a file or a command, never from memory. Client, people, platform and
document content are deliberately absent (see [anonymization.md](anonymization.md)).

Confidence labels: **proven** (read in a file or a command output), **probable** (consistent with the files, not measured), **not established** (no trace).

## 1. Summary

**What served, with evidence**
- A home-made script bench replayed a frozen question set × 2 user profiles over several model series with one status rule and blocking controls (`src/`).
- Process tooling gave traceability and a register of open questions (section 5).
- Blind audits caught what the mechanical rule could not (section 4).

**What is not established.** That generic lifecycle tooling helped the campaign (section 5). What carried it was local practice: one status rule, blocking tests,
independent re-derivation, blind audits.

**Key facts** (no campaign figures are published): the first full blind audit found every case in agreement with the mechanical status and no non-literal quote;
a later light audit covered all partials but only a fraction of the greens; no dollar total exists because usage was not returned and prices were unknown.

## 2. The bench

```
frozen questions (SHA-256) → collect through the back end's API → one JSON line per pass → one status module → comparison with blocking controls
   → workbook and deck (refuse to build if a test is red) → independent re-derivation of every delivered number → blind audit
```

| Stage | Guarantees that mattered |
|---|---|
| Collect | resume skips passes already `ok`; stop after 3 consecutive failures; question fingerprint in `meta.json`; keys read from the environment, never logged; the requested model label recorded on every line |
| Status | single module, total rule, governance written at the top of the file; no exception per profile, length or refusal wording |
| Compare | statistics computed only from journals, via the status module; the median recomputed twice; exit 1 on any discrepancy; journal hashes in the output |
| Deliver | workbook builder runs the status tests first and writes nothing if they fail; deck carries a provenance stamp |
| Verify | a second script re-reads the delivered files with patterns distinct from the status module; exit 1 on any gap |
| Audit | stratified draw with fixed seed, canaries, blind reviewers, adversary, literal-quote check (section 4) |

Rule of thumb that held: heavy work in scripts, LLM agents only for audits and reviews.

## 3. New client information

Every new fact became either a new test question (added with a duplicate check and an atomic write, replayed on two models × two profiles, workbooks rebuilt)
or a dated note with its source. The first version of that procedure still used an older browser-driven runner, so adding one question
silently changed the question fingerprint and made the new series non-comparable with the older ones. Lesson: when the question set changes, treat it as a new series,
state it, and route the procedure through the same collector and comparison as everything else.

## 4. Quality incidents and audits

**The wrong green.** A hand-made "refusal expected" exception ranked a sourceless answer Ok. Response, in order: remove the exception; one total rule; a test that forbids its return and blocks the
workbook build; independent re-derivation; blind audit with canaries. Details in [status-rule.md](status-rule.md).

**Audit designs actually used**

| Audit | Design | Result | Limit |
|---|---|---|---|
| Full (first series) | 3 blind reviewers of different model tiers × batches of about 22 cases, 3 canaries per batch, one adversary per batch, literal-quote check | all batches done, full agreement, no non-literal quote, no objection | 2 canaries recognised as fake; 30 remarks outside the criterion (cited sources unrelated to the topic, which the rule does not score) |
| Light (last series) | 1 reviewer, 2 passes: all 11 partials + 11 random greens + 2 control cases; then 30 greens stratified (5 per series × profile) + 2 control cases | 3 disagreements out of 24, then full agreement on 32 | citations not machine-checked, one reviewer, no adversary; **all partials covered but only about a fifth of the greens**; batch files were kept in a session scratch folder and lost; the report was written afterwards from transcripts |

The 3 disagreements of the light audit were "announcement" answers (a promise to search, 95 to 137 characters, no content): empty for a human reader, partial by the rule.
The owner kept the rule and added an explicit note to the deliverable instead of adding an exception.

**What the audits do not cover.** Relevance and correctness of the content and of the cited sources. Do not claim it.

**Lessons**
1. Write the audit report the same day. A reconstructed report is weaker evidence and the first version of this very report said "audit not finished" while a lighter audit had in fact been done.
2. Keep the batch files (or at least seed, config and counts) outside any ephemeral folder.
3. Count agents from all transcripts of the work: a session opened from another directory is stored elsewhere, and the first count was wrong.
4. Plausible canaries only. A marker that looks like a placeholder is spotted and proves little.
5. A sample of 5 greens per cell cannot detect an error rate of 10 to 15 %: state the coverage next to the result.

## 5. Process tooling around the bench

Generic project tooling (commit guards, source-reference discipline, an open-questions register, hand-over files, lifecycle plugins) surrounded the bench. What the files let us claim:
- **Proven**: guards forced traceability (every synthesis note pointed to its source; a ledger recorded what was blocked and why-not-recorded); the open-questions register kept doubts (served model behind a label, latency noise) from being filled with assumptions.
- **Weak use**: formal decision records stopped after the first days; hand-over, roadmap and journey files were not refreshed and would have misled a newcomer; a health check produced known false warnings.
- **Not established**: any measurable benefit of generic lifecycle tooling on test quality. The quality came from the practices in sections 2 and 4 (one rule, blocking tests, re-derivation, blind audit), which no tool imposed.
- **Home-made glue**: an automatic commit hook (no push, no hook bypass, drops sensitive and large files, replays the guards) produced most commits with uninformative messages and repeatedly dropped a harmless template as "sensitive" (false positive).
Report any claimed benefit of such tooling as "stated by the owner", separately from facts.

## 6. Cost

No dollar total (price unknown, token usage not returned by the platform: 4 probe requests out of 4 returned `usage: null`). Order of magnitude only: on the order of a thousand requests, about a million output tokens and two orders of magnitude more cache-read tokens. Model-call cost of the evaluated models was not found. The repo ships a range method instead
([cost-estimation.md](cost-estimation.md)).

## 7. Traps met when comparing several series

- Labels can carry a provider prefix, be accepted with a back-end error, or not exist at all (the model named another version when asked). No silent substitution; every line records the requested label.
- Series run in parallel inflate latency: timing columns were removed until a sequential run.
- A broad conflict detector blocked the comparison on a link without the citation marker; the owner decided "partial", recorded against the answer hash. The status rule was not touched.
- A provider key (retrieval bypass) served for two diagnostic calls only, never as a result.
- The verifier first assumed one `ok` line per id; replays create several. A test class placed after the `if __name__` guard never ran.

## 8. Recommendations

1. Log every agent and skill invocation (name, time, session) in project state, so "what helped" is a count.
2. Record the reason of each guard block in the ledger.
3. Route "new client information" through the current collector and comparison; handle the fingerprint change explicitly.
4. Refresh hand-over, roadmap and journey files automatically at each series or decision.
5. Fix false positives (health-check noise, sensitive-file heuristic on templates).
6. Run the full blind audit (3 reviewers, canaries, adversary, literal quotes) when a series backs a decision; the light one is for internal checks. Tooling: [../compound/README.md](../compound/README.md).
7. Score source relevance with a written criterion validated by the owner; never by an ad hoc exception.
8. Make automatic commit messages say what changed.
