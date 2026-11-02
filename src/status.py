"""SINGLE SOURCE OF TRUTH for answer statuses. Every script that classifies an answer imports this module.

The rule is total and has NO exception:
  Ko           no usable answer: technical failure, empty answer, or stream not finished (finish_reason != "stop").
  Ok           complete answer with at least one cited source marker in the text.
  Ok - partial complete answer with no cited source.

GOVERNANCE: no exception (per profile, per length, per refusal wording, ...) may be added without a written
criterion in the legend AND explicit validation by the project owner. The rule measures the PRESENCE of a
source, never the relevance of the answer (relevance needs a human or an LLM audit, see docs/quality-guards.md).
tests/test_status.py forbids the return of refusal-based exceptions.
"""
import json
import re

from config import load

OK, PART, KO = "Ok", "Ok - partial", "Ko"

_cfg = load()
SRC = re.compile(_cfg["source_pattern"])
BROAD = re.compile(_cfg["suspect_pattern"], re.I)

def configure(cfg):
    """Re-compile the two patterns from a loaded config (call once, before classifying, when the config sets custom patterns)."""
    global SRC, BROAD
    SRC = re.compile(cfg["source_pattern"])
    BROAD = re.compile(cfg["suspect_pattern"], re.I)


LEGEND = {
    OK: "complete answer with at least one source cited in the text.",
    PART: "answer delivered (stream finished, non-empty text) but no source cited: the agent answered without relying on an identified document.",
    KO: "no usable answer: error, empty or truncated answer.",
}


def sources(text):
    """Cited sources, de-duplicated, in order of appearance."""
    return list(dict.fromkeys(SRC.findall(text or "")))


def status(rec):
    """Status of one log record (dict): OK, PART or KO."""
    if not rec or rec.get("status") != "ok" or not (rec.get("response") or "").strip() or rec.get("finish_reason") != "stop":
        return KO
    return OK if sources(rec["response"]) else PART


def conflict(rec):
    """Message if the broad detector sees a source hint in a text ranked partial (rule to re-examine), else None."""
    if status(rec) == PART and BROAD.search(rec["response"]):
        return f"text ranked partial but containing a source hint: {BROAD.findall(rec['response'])[:3]}"
    return None


def load_log(path):
    """.jsonl journal -> {id: record}. Last "ok" line of an id if any, else its last line."""
    d = {}
    with open(path, encoding="utf8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if r["id"] not in d or r.get("status") == "ok" or d[r["id"]].get("status") != "ok":
                d[r["id"]] = r
    return d
