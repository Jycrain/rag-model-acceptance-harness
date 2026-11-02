"""Invariant tests of the status rule. Run: python3 tests/test_status.py (exit code 1 on any failure; build_excel.py calls it before writing).

HARNESS_CONFIG may point to a config; by default the demo dataset is used for the data tests.
"""
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
if not os.environ.get("HARNESS_CONFIG"):
    os.environ["HARNESS_CONFIG"] = str(ROOT / "examples" / "demo" / "config.json")
import conflicts  # noqa: E402
import status as S  # noqa: E402
from config import DEFAULTS, load  # noqa: E402


def rec(text, status="ok", finish="stop"):
    return {"status": status, "response": text, "finish_reason": finish}


SRC1 = "[src: kb-0001-opening-hours]"
SRC2 = "[src: kb-0002-loan-rules]"


class GoldenCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.configure(DEFAULTS)   # golden cases are written in the default citation convention, whatever the active config

    def test_short_refusal_without_source_is_partial(self):   # the case that motivated these tests: a refusal exception once ranked such an answer Ok
        self.assertEqual(S.status(rec("A short reply that cites nothing.")), S.PART)

    def test_same_sentence_with_sources_is_ok(self):
        self.assertEqual(S.status(rec(f"No public summary exists. See {SRC1} {SRC2}. Further detail is available on request.")), S.OK)

    def test_one_source_is_enough(self):
        self.assertEqual(S.status(rec(f"Answer {SRC2}")), S.OK)

    def test_empty_answer_is_ko(self):
        for t in ("", "   \n"):
            self.assertEqual(S.status(rec(t)), S.KO)

    def test_unfinished_stream_is_ko(self):
        self.assertEqual(S.status(rec(f"Answer {SRC1}", finish="length")), S.KO)

    def test_technical_failure_is_ko(self):
        for st in ("api_error", "timeout", "empty_response", "abnormal_end"):
            self.assertEqual(S.status(rec(f"x {SRC1}", status=st)), S.KO)

    def test_missing_record_is_ko(self):
        self.assertEqual(S.status(None), S.KO)

    def test_bare_url_is_not_a_source_but_raises_a_conflict(self):
        r = rec("See https://example.org/doc/x_1 for details.")
        self.assertEqual(S.status(r), S.PART)
        self.assertIsNotNone(S.conflict(r))

    def test_partial_without_hint_has_no_conflict(self):
        self.assertIsNone(S.conflict(rec("The library is a public service.")))

    def test_length_and_profile_change_nothing(self):
        short, long = rec("Reserved for members."), rec("Reserved for members. " * 200)
        self.assertEqual(S.status(short), S.status(long))
        self.assertEqual(S.status(short), S.PART)

    def test_load_log_keeps_the_ok_line_after_a_failed_attempt(self):
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"id": "01", "status": "timeout", "response": ""}) + "\n" + json.dumps({"id": "01", "status": "ok", "response": "x"}) + "\n")
        self.assertEqual(S.load_log(f.name)["01"]["status"], "ok")
        os.unlink(f.name)


class Governance(unittest.TestCase):
    def test_no_refusal_exception_in_the_classification_scripts(self):
        for f in ("status.py", "compare.py", "build_excel.py"):
            p = ROOT / "src" / f
            if not p.exists():
                continue
            code = re.sub(r"(?s)\"\"\".*?\"\"\"|#[^\n]*", "", p.read_text(encoding="utf8"))   # without docstrings and comments
            self.assertNotRegex(code, r"(?i)\brefus(al|e)\b|expected refusal|reserved for members", f"{f}: refusal exception detected")

    def test_legend_is_complete_and_exception_free(self):
        self.assertEqual(set(S.LEGEND), {S.OK, S.PART, S.KO})
        for v in S.LEGEND.values():
            self.assertNotRegex(v, r"(?i)refus|member|visitor")


class DemoData(unittest.TestCase):
    """Invariants on the journals of the active config: one ok line per question, exhaustive partition, Ok <=> source cited."""

    def test_partition_and_invariants(self):
        cfg = load()
        S.configure(cfg)
        self.assertTrue(cfg["series"] and cfg["profiles"], "empty config: this test would verify nothing")
        qids = [x["id"] for x in json.load(open(os.path.join(cfg["_dir"], cfg["questions"]), encoding="utf8"))]
        for name, spec in cfg["series"].items():
            for p in cfg["profiles"]:
                recs = S.load_log(os.path.join(cfg["_dir"], spec["dir"], p + ".jsonl"))
                self.assertEqual(sorted(recs), sorted(qids), f"{name}/{p}")
                for i, r in recs.items():
                    st = S.status(r)
                    self.assertIn(st, (S.OK, S.PART, S.KO))
                    self.assertEqual(st == S.OK, bool(S.sources(r["response"])), f"{name}/{p}/{i}")
                    if S.conflict(r):
                        self.assertTrue(conflicts.is_validated(spec["dir"], p, i, r), f"unsettled conflict {name}/{p}/{i}")


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=1).result
    sys.exit(0 if res.wasSuccessful() else 1)
