"""CI guard: the generic layer of the leak scanner must report nothing on the repo.

The PRIVATE layer (real client terms) is never run here: its list lives outside the repo. Run it locally:
  HARNESS_FORBIDDEN_FILE=~/.config/rag-harness/forbidden-terms.local python3 compound/scripts/anonymize_check.py --history
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class NoLeak(unittest.TestCase):
    def test_generic_scan_is_clean(self):
        env = {k: v for k, v in os.environ.items() if k != "HARNESS_FORBIDDEN_FILE"}
        r = subprocess.run([sys.executable, str(ROOT / "compound" / "scripts" / "anonymize_check.py"), str(ROOT)], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_scanner_catches_planted_leaks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            # planted strings are assembled at runtime so that this file never matches the scanner itself
            planted = " ".join(["contact bob" + "@" + "client-corp.fr,", "path /Us" + "ers/bob/x,", "id " + "-".join(["00000000", "1111", "2222", "3333", "444444444444"]) + ",", "host https://app-" + "prd.client.fr"])
            Path(d, "a.md").write_text(planted, encoding="utf8")
            r = subprocess.run([sys.executable, str(ROOT / "compound" / "scripts" / "anonymize_check.py"), d], capture_output=True, text=True, env={k: v for k, v in os.environ.items() if k != "HARNESS_FORBIDDEN_FILE"})
            self.assertEqual(r.returncode, 1)
            for kind in ("e-mail", "home path", "uuid", "internal host"):
                self.assertIn(kind, r.stdout)

    def test_private_terms_are_matched_without_being_echoed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            Path(d, "a.md").write_text("we worked for Zorglub Inc.", encoding="utf8")
            lst = Path(d, "list.txt")
            lst.write_text("zorglub\n", encoding="utf8")
            env = dict(os.environ, HARNESS_FORBIDDEN_FILE=str(lst))
            r = subprocess.run([sys.executable, str(ROOT / "compound" / "scripts" / "anonymize_check.py"), d], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 1)
            self.assertNotIn("zorglub", r.stdout.lower().replace("private list", ""))


if __name__ == "__main__":
    res = unittest.main(exit=False, verbosity=1).result
    sys.exit(0 if res.wasSuccessful() else 1)
