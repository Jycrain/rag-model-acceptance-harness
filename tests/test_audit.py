"""Tests of the audit consensus: literal quotes, objections, canaries. Run: python3 tests/test_audit.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = str(ROOT / "src" / "audit_consensus.py")
OK = {"has_source": True, "complete_answer": True}


def run(tmp, key, reviews, pack=None, objections=None):
    files = []
    for i, r in enumerate(reviews):
        p = Path(tmp) / f"r{i}.json"
        p.write_text(json.dumps(r))
        files.append(str(p))
    (Path(tmp) / "key.json").write_text(json.dumps(key))
    cmd = [sys.executable, "-I", SCRIPT, str(Path(tmp) / "key.json"), *files]
    if pack is not None:
        (Path(tmp) / "pack.json").write_text(json.dumps(pack))
        cmd += ["--pack", str(Path(tmp) / "pack.json")]
    if objections is not None:
        (Path(tmp) / "obj.json").write_text(json.dumps(objections))
        cmd += ["--objections", str(Path(tmp) / "obj.json")]
    return subprocess.run(cmd, capture_output=True, text=True)


KEY = {"c1": {"pipeline_status": "Ok", "canary": None, "origin": "x"}}
PACK = {"cases": [{"case": "c1", "question": "q", "answer": "The loan period is 21 days **DOC_1_a.txt**"}]}


class Consensus(unittest.TestCase):
    def test_agreement_passes(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(run(t, KEY, [{"c1": OK}, {"c1": OK}]).returncode, 0)

    def test_literal_quote_passes(self):
        with tempfile.TemporaryDirectory() as t:
            r = {"c1": {**OK, "quotes": ["loan period is 21 days"]}}
            self.assertEqual(run(t, KEY, [r], pack=PACK).returncode, 0)

    def test_paraphrased_quote_fails(self):
        with tempfile.TemporaryDirectory() as t:
            r = {"c1": {**OK, "quotes": ["loans last three weeks"]}}
            p = run(t, KEY, [r], pack=PACK)
            self.assertEqual(p.returncode, 1)
            self.assertIn("NON-LITERAL QUOTE", p.stdout)

    def test_objection_blocks_agreement(self):
        with tempfile.TemporaryDirectory() as t:
            p = run(t, KEY, [{"c1": OK}], objections={"c1": "source unrelated"})
            self.assertEqual(p.returncode, 1)
            self.assertIn("OBJECTION", p.stdout)

    def test_missed_canary_fails(self):
        key = {"c1": {"pipeline_status": "Ok - partial", "canary": "stripped", "origin": "x"}}
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(run(t, key, [{"c1": OK}]).returncode, 1)


if __name__ == "__main__":
    unittest.main()
