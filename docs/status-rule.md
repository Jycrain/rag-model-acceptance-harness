# The status rule (single source of truth)

Implemented once, in [`src/status.py`](../src/status.py). Every script imports it; no script re-implements it.

| Status | Colour | Definition |
|---|---|---|
| **Ok** | green | complete answer (finished: `finish_reason == "stop"` for streams, the adapter's finish mapping or a clean exit otherwise; non-empty text) **with at least one cited source marker** |
| **Ok - partial** | orange | complete answer **without any cited source marker** |
| **Ko** | red | no usable answer: technical failure (`status != ok`), empty text, or stream not finished |

## What it measures, and what it does not

It measures the **presence of a cited source**. It does not judge relevance, correctness or completeness of content.
A cited but irrelevant source is Ok; a correct answer that cites nothing is Ok - partial. Say so in every legend.

## Declaring what a "cited source" is

The convention is whatever your system prints, declared once in the config (`citation` block, see `src/config.py`):

| Preset | A cited source looks like | Use when |
|---|---|---|
| `bracket_id` (default) | `[src: kb-0427-handbook]` | you control the system prompt and can ask for it |
| `bracket_number` | `[3]` | the system numbers its references |
| `markdown_link` | `[Handbook](https://docs.example.net/handbook)` | the system answers with links |
| `bold_prefixed` | `**DOC_12_guide.txt**` (bold text starting with a known id prefix; `prefixes` are regex fragments) | the system bolds document ids |
| `custom` | your own `source_pattern` (one capture group) | anything else |

Each preset brings a broad `suspect_pattern`, a plausible `canary_marker` for audits and a second, independent marker-counting pattern
(`source_marker_start_pattern`) used by `compare.py` as a cross-check. If your system returns structured sources instead of text, convert them to
the chosen convention in an adapter (or request that the model prints them) so that the same rule applies.

## No exceptions: the governance rule

> No special case (per profile, per length, per refusal wording, per theme…) may enter a classification rule without a
> written criterion in the legend **and** explicit validation by the project owner.

Why: a plausible-looking exception once shipped a wrong green. The story is in [lessons-learned.md](lessons-learned.md).

How it is enforced:
- `tests/test_status.py` contains golden cases (including the one that motivated the rule) and a test that scans the
  classification scripts for refusal-based exceptions (docstrings/comments stripped, so documentation may mention them).
- `src/build_excel.py` refuses to write if those tests fail.
- `src/verify_deliverables.py` re-derives every status with a second, deliberately naive implementation.

## Broad detector and signed decisions

`status.conflict()` uses a *broad* regex (any URL, `.txt`, marker prefix…). It never classifies. If an answer ranked
"partial" still contains such a hint (e.g. a bare URL instead of a marker), the build **blocks** until the owner decides.
The decision is recorded in `validated_conflicts.json`, tied to the SHA-256 of the exact answer text: if the journal is
replayed and the answer changes, the conflict blocks again. A decision never changes a status; it only authorises delivery.

## Announcement answers (a known gap of the rule)

A model may answer only "I am consulting the knowledge base…" and stop. The rule ranks it by the same logic (no source →
partial) which is right, but a human reads it as *empty*. The blind audit flagged exactly these. The decision taken: keep the
rule, add an explicit note to the deliverable. A rule change would need a written criterion and owner validation.
