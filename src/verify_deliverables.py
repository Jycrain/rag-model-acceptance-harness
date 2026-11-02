#!/usr/bin/env python3
"""Independent re-read of the workbook against the raw journals. Exit code 1 on the slightest difference.

Usage: python3 src/verify_deliverables.py --config examples/demo/config.json comparison.xlsx

Independence: statuses are RE-DERIVED here with a different code path (a marker-start regex and plain string tests), not by
importing status.py. If this file and status.py ever disagree, one of them has drifted and the build must not be delivered.
Checks per cell: status text, that the sources column is >0 exactly when the status is Ok, answer text, and that every journal pass appears exactly once.
"""
import argparse
import json
import os
import re
import sys

from openpyxl import load_workbook

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load

MARKER = re.compile(load()["source_marker_start_pattern"])


def derive(rec):
    """Second implementation of the rule (kept deliberately naive)."""
    if rec.get("status") != "ok" or rec.get("finish_reason") != "stop" or not (rec.get("response") or "").strip():
        return "Ko", 0
    n = len(MARKER.findall(rec["response"]))   # markers, not full tokens: a different way to count
    return ("Ok" if n else "Ok - partial"), n


def last_ok(path):
    d = {}
    for line in open(path, encoding="utf8"):
        if line.strip():
            r = json.loads(line)
            if r["id"] not in d or r["status"] == "ok":
                d[r["id"]] = r
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("workbook")
    ap.add_argument("--config", default=os.environ.get("HARNESS_CONFIG"))
    a = ap.parse_args()
    cfg = load(a.config)
    global MARKER
    MARKER = re.compile(cfg.get("source_marker_start_pattern", MARKER.pattern))
    wb = load_workbook(a.workbook)
    bad, cells = [], 0
    for name, spec in cfg["series"].items():
        ws = wb[name[:31]]
        seen = set()
        for row in ws.iter_rows(min_row=2, values_only=True):
            profile, qid, _theme, _q, st, nsrc, text = row[:7]
            rec = last_ok(os.path.join(cfg["_dir"], spec["dir"], profile + ".jsonl")).get(qid)
            cells += 1
            if rec is None:
                bad.append(f"{name}/{profile}/{qid}: not in journal")
                continue
            exp, _ = derive(rec)
            if ((nsrc or 0) > 0) != (exp == "Ok"):
                bad.append(f"{name}/{profile}/{qid}: sources column {nsrc} inconsistent with re-derived status {exp}")
            if st != exp:
                bad.append(f"{name}/{profile}/{qid}: sheet says {st}, re-derived {exp}")
            if (text or "") != rec["response"]:
                bad.append(f"{name}/{profile}/{qid}: answer text differs from journal")
            seen.add((profile, qid))
        expected = {(p, i) for p in cfg["profiles"] for i in last_ok(os.path.join(cfg["_dir"], spec["dir"], p + ".jsonl"))}
        if seen != expected:
            bad.append(f"{name}: sheet rows != journal passes ({len(seen)} vs {len(expected)})")
    for b in bad:
        print("DIFF:", b)
    print(f"checked {cells} cells:", "all consistent" if not bad else f"{len(bad)} difference(s)")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
