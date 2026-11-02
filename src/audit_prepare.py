#!/usr/bin/env python3
"""Draws a STRATIFIED, BLIND audit sample and writes review packs for independent LLM (or human) reviewers.

Usage: python3 src/audit_prepare.py --config examples/demo/config.json --per-cell 5 --seed 42 --out audit/
Stratification: for every (series, profile) cell, ALL "partial" answers plus `--per-cell` randomly drawn "Ok" answers
(fixed seed => reproducible), plus 2 canaries per run (an Ok answer with its source markers stripped, and a partial answer
with a fake marker injected) that a reviewer who really reads must catch. A simple random draw over all green answers is NOT
enough: it can leave a whole (series, profile) cell unchecked (this happened once, see docs/lessons-learned.md).

Blind: the pack shows question + answer + the citation convention only, never the status the pipeline assigned.
Writes <out>/pack.json (what reviewers see; opaque case ids) and <out>/key.json (origin, pipeline status and canary flag, read only by audit_consensus.py).
The injected canary marker must be plausible and match your citation convention: the citation presets provide one; set "canary_marker" in the config's citation block for custom conventions.
"""
import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import status as S
from config import load


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.environ.get("HARNESS_CONFIG"))
    ap.add_argument("--per-cell", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="audit")
    ap.add_argument("--batch-size", type=int, default=0, help="also write <out>/batches/batch-NN.json of this size (0 = no batches)")
    a = ap.parse_args()
    cfg = load(a.config)
    S.configure(cfg)
    MARKER = cfg.get("canary_marker")
    if not MARKER:
        sys.exit('set "canary_marker" in the config (citation block): a plausible marker in your citation convention, injected into canary answers')
    rnd = random.Random(a.seed)
    pack, key, counter = [], {}, [0]

    def new_id():
        counter[0] += 1
        return f"case-{counter[0]:03d}"   # opaque: reveals neither series, profile nor canary
    for name, spec in cfg["series"].items():
        for p in cfg["profiles"]:
            recs = S.load_log(os.path.join(cfg["_dir"], spec["dir"], p + ".jsonl"))
            partial = [r for r in recs.values() if S.status(r) == S.PART]
            green = [r for r in recs.values() if S.status(r) == S.OK]
            chosen = partial + rnd.sample(green, min(a.per_cell, len(green)))
            for r in chosen:
                cid = new_id()
                pack.append({"case": cid, "question": r["question"], "answer": r["response"]})
                key[cid] = {"pipeline_status": S.status(r), "canary": None, "origin": f"{name}|{p}|{r['id']}"}
            canary_ok = rnd.choice(green) if green else None
            if canary_ok:
                cid = new_id()
                pack.append({"case": cid, "question": canary_ok["question"], "answer": re.sub(S.SRC, "", canary_ok["response"])})
                key[cid] = {"pipeline_status": S.PART, "canary": "markers stripped from an Ok answer: must be judged without source", "origin": f"{name}|{p}|{canary_ok['id']}"}
            if partial:
                r = rnd.choice(partial)
                cid = new_id()
                pack.append({"case": cid, "question": r["question"], "answer": r["response"] + " " + MARKER})
                key[cid] = {"pipeline_status": S.OK, "canary": "fake marker injected into a partial answer: must be judged with a source", "origin": f"{name}|{p}|{r['id']}"}
    rnd.shuffle(pack)
    os.makedirs(a.out, exist_ok=True)
    json.dump({"citation_convention": cfg["source_pattern"], "cases": pack}, open(os.path.join(a.out, "pack.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(key, open(os.path.join(a.out, "key.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if a.batch_size > 0:
        os.makedirs(os.path.join(a.out, "batches"), exist_ok=True)
        for n in range(0, len(pack), a.batch_size):
            json.dump({"citation_convention": cfg["source_pattern"], "cases": pack[n:n + a.batch_size]},
                      open(os.path.join(a.out, "batches", f"batch-{n // a.batch_size + 1:02d}.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(f"{len(pack)} cases written to {a.out}/pack.json (key in key.json, do NOT show it to reviewers)")


if __name__ == "__main__":
    main()
