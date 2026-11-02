#!/usr/bin/env python3
"""Builds the comparison workbook: one "Summary" sheet (models x profiles) + one detail sheet per series.

Usage: python3 src/build_excel.py --config examples/demo/config.json --out comparison.xlsx
Requires: openpyxl. Statuses come ONLY from status.py. Timing columns are deliberately absent by default
(--with-timing adds them): delays measured with series running in parallel are not clean and mislead readers.
Refuses to write if tests/test_status.py fails (blocking guard).
"""
import argparse
import os
import subprocess
import sys

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import status as S
from config import load

COLORS = {S.OK: ("C8F5D6", "0D5A2E"), S.PART: ("FFB95C", "3D2100"), S.KO: ("FFDAD6", "BA1A1A")}


def cell_style(c, st):
    bg, fg = COLORS[st]
    c.fill, c.font = PatternFill("solid", fgColor=bg), Font(color=fg, bold=True)


def text_cell(c, value):
    """Write text that must never be interpreted as a formula (answers can start with = + - @)."""
    c.value = value
    if isinstance(value, str):
        c.data_type = "s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.environ.get("HARNESS_CONFIG"))
    ap.add_argument("--out", default="comparison.xlsx")
    ap.add_argument("--with-timing", action="store_true")
    a = ap.parse_args()
    env = dict(os.environ)
    if a.config:
        env["HARNESS_CONFIG"] = a.config
    t = subprocess.run([sys.executable, os.path.join(HERE, "..", "tests", "test_status.py")], env=env, capture_output=True, text=True)
    if t.returncode:
        sys.exit("status tests failed: refusing to build\n" + t.stdout[-1500:] + t.stderr[-1500:])
    cfg = load(a.config)
    S.configure(cfg)
    base, profiles = cfg["_dir"], list(cfg["profiles"])
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.append(["Model"] + [f"{p} - {lab}" for p in profiles for lab in (S.OK, S.PART, S.KO)] + ["Total Ok", "Total passes"])
    detail = {}
    for name, spec in cfg["series"].items():
        logs = {p: S.load_log(os.path.join(base, spec["dir"], p + ".jsonl")) for p in profiles}
        detail[name] = logs
        counts = {p: [sum(1 for r in logs[p].values() if S.status(r) == s) for s in (S.OK, S.PART, S.KO)] for p in profiles}
        total = sum(len(v) for v in logs.values())
        ws.append([cfg["models"][spec["model"]].get("name", name)] + [n for p in profiles for n in counts[p]] + [sum(counts[p][0] for p in profiles), total])
    ws.append([])
    ws.append(["Legend"])
    for st, text in S.LEGEND.items():
        ws.append([st, text])
        cell_style(ws.cell(ws.max_row, 1), st)
    ws.append(["Note", "The status measures the presence of a cited source, not the relevance of the answer."])
    ws.column_dimensions["A"].width = 22
    for sheet_name, logs in detail.items():
        d = wb.create_sheet(sheet_name[:31])
        head = ["Profile", "Id", "Theme", "Question", "Status", "Sources cited", "Answer"] + (["TTFT (s)", "Duration (s)"] if a.with_timing else [])
        d.append(head)
        for c in d[1]:
            c.font = Font(bold=True)
        for p in profiles:
            for qid in sorted(logs[p]):
                r = logs[p][qid]
                row = [p, qid, r["theme"], r["question"], S.status(r), len(S.sources(r["response"])), r["response"]] + ([r["ttft_s"], r["duration_s"]] if a.with_timing else [])
                d.append(row)
                for col in (4, 7):
                    text_cell(d.cell(d.max_row, col), row[col - 1])
                cell_style(d.cell(d.max_row, 5), S.status(r))
                d.cell(d.max_row, 7).alignment = Alignment(wrap_text=True, vertical="top")
        for i, w in enumerate([10, 6, 16, 44, 14, 8, 80, 10, 12], 1):
            d.column_dimensions[get_column_letter(i)].width = w
        d.freeze_panes = "A2"
        d.auto_filter.ref = d.dimensions
    wb.save(a.out)
    print("written", a.out)


if __name__ == "__main__":
    main()
