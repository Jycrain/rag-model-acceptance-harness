"""End-to-end collection with the `command` adapter (no network, no secrets): collect -> journal -> status -> resume.

Run: python3 tests/test_collect_e2e.py   (needs Node 18+)
The "back end" is a one-line Node program: it answers with a source marker unless the question contains "nosource".
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import status as S  # noqa: E402
from config import load  # noqa: E402

FAKE = "let q='';process.stdin.on('data',d=>q+=d).on('end',()=>process.stdout.write(q.includes('nosource')?'A plain answer.':'An answer [src: kb-9-demo].'))"


@unittest.skipUnless(shutil.which("node"), "node not installed")
class CollectEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        t = Path(self.tmp)
        (t / "questions.json").write_text(json.dumps([
            {"id": "01", "n": 1, "theme": "t", "q": "first question"},
            {"id": "02", "n": 2, "theme": "t", "q": "second nosource question"},
        ]))
        (t / "config.json").write_text(json.dumps({
            "api": {"type": "command", "command": [shutil.which("node"), "-e", FAKE]},
            "questions": "questions.json",
            "profiles": {"p": {}},
            "models": {"m": {"label": "demo-label", "name": "M"}},
            "series": {"m": {"dir": "runs/m", "model": "m"}},
            "timing": {"pauseMs": 0, "timeoutMs": 20000, "retries": 0, "consecErrMax": 3},
        }))

    def tearDown(self):
        import config
        config._LAST = None   # do not leak this temporary config path into other tests of the same process
        shutil.rmtree(self.tmp, ignore_errors=True)

    def collect(self):
        return subprocess.run(["node", str(ROOT / "src" / "run_api.js"), "--config", str(Path(self.tmp) / "config.json"), "--profile", "p", "--model", "m"],
                              capture_output=True, text=True)

    def test_collect_status_and_resume(self):
        r = self.collect()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        cfg = load(str(Path(self.tmp) / "config.json"))
        S.configure(cfg)
        log = S.load_log(str(Path(self.tmp) / "runs" / "m" / "p.jsonl"))
        self.assertEqual(S.status(log["01"]), S.OK)
        self.assertEqual(S.status(log["02"]), S.PART)
        meta = json.loads((Path(self.tmp) / "runs" / "m" / "meta.json").read_text())
        self.assertEqual(meta["requested_model"], "demo-label")
        self.assertEqual(meta["channel"], "command")
        again = self.collect()
        self.assertIn("already done", again.stdout)
        self.assertEqual(len((Path(self.tmp) / "runs" / "m" / "p.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
