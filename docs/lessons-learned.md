# Lessons learned

Each item: what happened, why it mattered, what the repo now does about it. Details of the originating campaign are deliberately generic.

## 1. A hand-made exception shipped a wrong green
An "expected refusal" exception (short answer, restricted-profile wording) ranked a sourceless answer Ok. It looked reasonable and was wrong: replaying the
same question ten times showed that the first draw was atypical and the exception hid it. → single status module, golden test, test forbidding the exception,
independent re-derivation, blind audit, written governance rule ([status-rule.md](status-rule.md)). **A status describes a draw, not the model.**

## 2. The first audit sample was not stratified
A simple random draw over all green answers left some (series, profile) cells unchecked.
→ stratified draw with fixed seed and canaries (`audit_prepare.py`), redone before delivery. Admit it when it happens.

## 3. Timings from parallel series are not measurements
Series run concurrently inflate latency (median time-to-first-token rose noticeably and some passes crossed a latency threshold).
→ timing columns removed from detail sheets (with a note) until a clean sequential run; `--with-timing` is opt-in in `build_excel.py`.

## 4. "Announcement" answers
Some answers are only a promise ("I am consulting the knowledge base…"). Rule: partial. Human reading: empty. A blind audit flagged a few.
→ rule kept, explicit note in the deliverable, and a question to the system's owner about its prompt.

## 5. A provider key bypasses the application
A model provider's key is tempting to "unblock" a model, but it measures the model alone, not the application (retrieval, prompts, guard-rails).
→ principle 1 in [methodology.md](methodology.md); results only through the system's own credentials; direct calls are throw-away diagnostics.

## 6. The served model is not observable
Most APIs return no reliable served-model field, and a model may name another version when asked. → label probe with a failing control, and a request to
the owner of the back end for a console/log check. Keep "routing not verified from the API" as a stated limit.

## 7. Invalid early series
An early pilot used the wrong credentials, another an expired session whose back-end errors were counted "ok".
→ every journal line carries its HTTP status and error body; `ok` requires a finished stream; the comparison fails on mixed labels.

## 8. Labels change between series
Labels can be renamed or removed, and an accepted label can start failing after a back-end change. → re-probe before each series; record `requested_model` in every line and in `meta.json`.

## 9. Tool and process traps
- macOS `sed -i` needs `''`; when scripting Office apps, close the workbook/deck **by name** after a build.
- Run long jobs detached with sleep prevention; keep scripts resumable.
- Auto-commit hooks and agent plugins can write files into a repo (tool caches holding session ids and home paths): ignore them and let the leak scanner
  look at **what would be published** (`git ls-files -co --exclude-standard`).
- A leak scanner must not contain the secrets it looks for: the list of real client terms stays outside the repo.
- A test class defined after an `if __name__ == "__main__"` guard never runs; a verifier that assumes one journal line per id breaks as soon as replays exist.

## 10. Process
- Every new piece of client information becomes either a new test question or a dated note; nothing stays only in chat. A changed question set is a **new series**, not a patch of the old one.
- When blocked by a decision that belongs to the owner (is this partial or ok?), stop and ask with one concrete recommendation.
- Heavy work (collection) in scripts; sub-agents for audits and reviews, so the main context stays clean.

## 11. A light audit still needs its report, its seed and its batches
A light audit (one reviewer, two passes, a fifth of the greens covered) had no written report; batch files lived in an ephemeral working folder and were lost, and a later
retrospective wrongly called the audit "not finished". → write the audit report the same day, keep seed + config + counts, state coverage and limits next to the result
(see [rex.md](rex.md), skill `blind-audit`).

## 12. Agents counted in the wrong place
Agent usage was counted from one location only, while the work had been done from another.
→ count from every transcript of the work before writing "no agent was used".

## 13. Plausible canaries, literal quotes, an adversary
Canaries that look like placeholders are spotted. Reviewer quotes must be verbatim substrings of the answer (`audit_consensus.py --pack`), otherwise the reviewer did not read.
An adversary that receives the verdict matrix finds what independent reviewers share as a blind spot. → `prompts/`, `compound/agents/`, `compound/workflows/blind-audit.workflow.js`.
