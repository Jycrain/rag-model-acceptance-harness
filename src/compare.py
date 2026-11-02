#!/usr/bin/env python3
"""Statistics per series, computed ONLY from the .jsonl journals; statuses come ONLY from status.py (single rule).

Usage: python3 src/compare.py --config examples/demo/config.json [--out stats.json]
Writes stats.json and exits with code 1 on the slightest inconsistency (a blocking guard, not a warning).

Controls run for every series:
  - exactly one "ok" pass per (profile, question), no more, no less;
  - requested model label in meta.json == label in config == label in every log line;
  - every finish_reason is "stop", no empty answer;
  - cited sources counted by two independent methods must agree;
  - a "partial" answer with a source hint must have a signed decision (conflicts.py) or the build is blocked;
  - question-set fingerprints (SHA-256) identical across series (same questions for every model).
"""
import argparse
import hashlib
import json
import os
import re
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import conflicts
import status as S
from config import load
from gaps import GAP

errors = []


def fail(msg):
    errors.append(msg)
    print("MISMATCH:", msg)


def median_by_hand(v):
    s = sorted(v)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def aggregate(rows):
    rows = list(rows)
    if not rows:
        return {"n": 0}
    ttft = [r["ttft_s"] for r in rows if r["ttft_s"] is not None]
    dur = [r["duration_s"] for r in rows]
    if ttft and abs(statistics.median(ttft) - median_by_hand(ttft)) > 1e-9:
        fail("TTFT median differs between two methods")
    st = [S.status(r) for r in rows]
    if st.count(S.OK) + st.count(S.PART) + st.count(S.KO) != len(rows):
        fail("the three statuses do not add up to the number of passes")
    return {
        "n": len(rows), "ok": st.count(S.OK), "partial": st.count(S.PART), "ko": st.count(S.KO),
        "gaps_signalled": sum(1 for r in rows if GAP.search(r["response"])),
        "ttft_median": round(statistics.median(ttft), 1) if ttft else None, "ttft_max": max(ttft) if ttft else None,
        "duration_median": round(statistics.median(dur), 1), "duration_max": max(dur),
        "over_40s": sum(1 for r in rows if (r["ttft_s"] or 0) > 40),
        "replays": sum(1 for r in rows if r.get("attempts", 1) > 1),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.environ.get("HARNESS_CONFIG"))
    ap.add_argument("--out", default="stats.json")
    a = ap.parse_args()
    cfg = load(a.config)
    S.configure(cfg)
    base = cfg["_dir"]
    profiles = list(cfg["profiles"])
    qids = [x["id"] for x in json.load(open(os.path.join(base, cfg["questions"]), encoding="utf8"))]
    stats, data = {"series": {}, "meta": {}, "validated_conflicts": []}, {}

    for name, spec in cfg["series"].items():
        run_dir = spec["dir"]
        ok, non_ok, raw = {}, 0, 0
        for p in profiles:
            f = os.path.join(base, run_dir, p + ".jsonl")
            if not os.path.exists(f):
                fail(f"journal missing: {run_dir}/{p}")
                continue
            for line in open(f, encoding="utf8"):
                x = json.loads(line)
                raw += 1
                if x["status"] == "ok":
                    if (p, x["id"]) in ok:
                        fail(f"{name}: duplicate ok pass for {p}/{x['id']}")
                    ok[(p, x["id"])] = x
                else:
                    non_ok += 1
        data[name] = ok
        if set(ok) != {(p, i) for p in profiles for i in qids}:
            fail(f"{name}: passes missing or in excess")
        meta = json.load(open(os.path.join(base, run_dir, "meta.json"), encoding="utf8"))
        wanted = cfg["models"][spec["model"]]["label"]
        if meta.get("requested_model") != wanted:
            fail(f"{name}: requested label {meta.get('requested_model')} != {wanted}")
        if {x["requested_model"] for x in ok.values()} != {wanted}:
            fail(f"{name}: mixed labels in the journal")
        stats["meta"][name] = {
            "requested_model": meta.get("requested_model"), "questions_sha256": meta.get("questions_sha256"),
            "raw_lines": raw, "non_ok_lines": non_ok,
            "first": min((x["start"] for x in ok.values()), default=None), "last": max((x["end"] for x in ok.values()), default=None),
            "returned_model": sorted({m for x in ok.values() for m in x.get("returned_model", [])}),
        }
        for (p, i), x in ok.items():
            if x.get("finish_reason") != "stop":
                fail(f"{name} {p}/{i} finish_reason={x.get('finish_reason')}")
            if not x["response"].strip():
                fail(f"{name} {p}/{i} empty answer")
            if len(S.SRC.findall(x["response"])) != len(re.findall(cfg["source_marker_start_pattern"], x["response"])):
                fail(f"{name} {p}/{i} sources: two counting methods disagree")
            c = S.conflict(x)
            if c:
                if conflicts.is_validated(run_dir, p, i, x):
                    stats["validated_conflicts"].append([name, p, i])
                else:
                    fail(f"{name} {p}/{i}: {c}")
        stats["series"][name] = {"total": aggregate(ok.values()), "by_profile": {p: aggregate(v for (pp, i), v in ok.items() if pp == p) for p in profiles}}

    hashes = {n: m["questions_sha256"] for n, m in stats["meta"].items()}
    if len(set(hashes.values())) > 1:
        fail(f"question-set fingerprints differ: {hashes}")
    stats["statuses"] = {n: {p: {i: S.status(x) for (pp, i), x in d.items() if pp == p} for p in profiles} for n, d in data.items()}
    stats["partials"] = {n: sorted([p, i] for (p, i), x in d.items() if S.status(x) == S.PART) for n, d in data.items()}
    stats["journal_sha256"] = {n: {p: hashlib.sha256(open(os.path.join(base, cfg["series"][n]["dir"], p + ".jsonl"), "rb").read()).hexdigest() for p in profiles} for n in data}
    stats["controls_ok"] = not errors
    json.dump(stats, open(os.path.join(base, a.out), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    for n, s in stats["series"].items():
        print(n, json.dumps(s["total"], ensure_ascii=False))
    print("CONTROLS:", "all green" if not errors else f"{len(errors)} mismatch(es)")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
