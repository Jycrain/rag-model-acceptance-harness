"""Conflicts raised by the broad detector (status.conflict) and settled by the project owner.

A decision is valid only for the EXACT answer (SHA-256): if the journal changes, the conflict blocks again.
A decision NEVER changes a status (status.py stays the only rule): it only allows the deliverable to be produced.

File format (validated_conflicts.json, next to the config):
  [{"dir": "runs/model-a", "profile": "member", "id": "02", "response_sha256": "...", "decided_status": "Ok - partial", "note": "..."}]
"""
import hashlib
import json
import os

from config import load


def _decisions():
    cfg = load()
    path = os.path.join(cfg["_dir"], cfg.get("validated_conflicts", "validated_conflicts.json"))
    return json.load(open(path, encoding="utf8")) if os.path.exists(path) else []


def is_validated(run_dir, profile, qid, rec):
    h = hashlib.sha256(rec["response"].encode()).hexdigest()
    key = (run_dir, profile, qid, h, "Ok - partial")
    return next((c for c in _decisions() if (c["dir"], c["profile"], c["id"], c["response_sha256"], c["decided_status"]) == key), None)
