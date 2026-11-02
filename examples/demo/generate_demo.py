#!/usr/bin/env python3
"""Generates the SYNTHETIC demo dataset (a fictional municipal library assistant). Deterministic, no real data.

Usage: python3 examples/demo/generate_demo.py
Writes questions.json, config.json, validated_conflicts.json and runs/<series>/<profile>.jsonl + meta.json next to this file.
The cases are chosen to exercise every branch of the pipeline: Ok, Ok - partial, a retry after a technical failure,
an "announcement" answer (promise to search, no content), and an unmarked link that raises a conflict.
"""
import hashlib
import json
import os
import random
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
random.seed(42)

TOPICS = [
    ("opening hours", "What are the opening hours of the central library?", "The central library opens Tuesday to Saturday, 10:00 to 18:00."),
    ("membership", "How do I register for a library card?", "Registration takes five minutes at the desk with a proof of address."),
    ("loans", "How many books can I borrow at once?", "A member can borrow up to ten books for four weeks."),
    ("renewal", "Can I renew a loan online?", "Loans can be renewed twice online unless another member reserved the item."),
    ("fines", "What happens if I return a book late?", "A late return blocks new loans until the book is back; there is no monetary fine."),
    ("digital", "Is there an e-book service?", "E-books are available through the digital portal with the same card."),
    ("rooms", "Can I book a study room?", "Study rooms can be booked for two hours, up to a week ahead."),
    ("events", "Where can I find the programme of events?", "The monthly programme is published on the events page."),
    ("donations", "Can I donate books?", "Donations are accepted on Wednesdays after a quick condition check."),
    ("accessibility", "Is the central library accessible to wheelchair users?", "The building is fully step-free with a lift to every floor."),
]
PROFILES = ["member", "visitor"]
MODELS = {"model-a": "demo-model-a-1", "model-b": "demo-model-b-2", "model-c": "demo-model-c-3"}


def src(i): return f"**DOC_{1000 + i}_library_guide.txt**"


def answer(model, profile, i, topic):
    base = TOPICS[i][2]
    kind = "ok"
    if model == "model-a" and (profile, i) == ("visitor", 7): kind = "partial"
    if model == "model-b" and (profile, i) in {("member", 3), ("visitor", 4)}: kind = "partial"
    if model == "model-b" and (profile, i) == ("member", 5): kind = "announcement"
    if model == "model-b" and (profile, i) == ("visitor", 8): kind = "unmarked_link"
    if model == "model-c" and (profile, i) == ("member", 1): kind = "retry"
    if kind in ("ok", "retry"): return kind, f"{base} See {src(i)}."
    if kind == "partial": return kind, f"{base} Please ask the desk for details."
    if kind == "announcement": return kind, "I am consulting the knowledge base to find the answer."
    return kind, f"{base} More at https://library.example.org/page/{i}."


def main():
    qs = [{"id": f"{i + 1:02d}", "n": i + 1, "theme": t, "q": q} for i, (t, q, _) in enumerate(TOPICS)]
    json.dump(qs, open(os.path.join(HERE, "questions.json"), "w"), indent=1)
    qhash = hashlib.sha256("\n".join(x["id"] + "\t" + x["q"] for x in qs).encode()).hexdigest()
    cfg = {
        "api": {"type": "openai_chat_sse", "base_url_env": "RAG_BASE_URL", "route": "/v1/chat/completions"},
        "citation": {"preset": "bold_prefixed", "prefixes": ["DOC_\\d+_"], "canary_marker": "**DOC_4821_borrowing_rules.txt**"},
        "questions": "questions.json",
        "profiles": {p: {"api_key_env": f"RAG_API_KEY_{p.upper()}"} for p in PROFILES},
        "models": {m: {"label": lab, "name": m.replace("model-", "Model ").upper().replace("MODEL ", "Model ")} for m, lab in MODELS.items()},
        "series": {m: {"dir": f"runs/{m}", "model": m} for m in MODELS},
        "validated_conflicts": "validated_conflicts.json",
        "prices_per_mtok": {m: {"input": 0.1 * (k + 1), "output": 0.4 * (k + 1), "currency": "EUR", "source": "placeholder, not a real price"} for k, m in enumerate(MODELS)},
    }
    json.dump(cfg, open(os.path.join(HERE, "config.json"), "w"), indent=1)
    decisions = []
    t0 = datetime(2026, 1, 15, 9, 0, 0)
    for mk, label in MODELS.items():
        d = os.path.join(HERE, "runs", mk)
        os.makedirs(d, exist_ok=True)
        json.dump({"model": mk, "requested_model": label, "channel": "api", "questions_sha256": qhash, "n_questions": len(qs), "key_tail": "…demo"}, open(os.path.join(d, "meta.json"), "w"), indent=1)
        for p in PROFILES:
            lines = []
            for i, q in enumerate(qs):
                kind, text = answer(mk, p, i, TOPICS[i])
                t0 += timedelta(seconds=12)
                rec = {"channel": "api", "id": q["id"], "n": q["n"], "theme": q["theme"], "question": q["q"], "profile": p, "model": mk, "requested_model": label,
                       "start": t0.isoformat(), "end": (t0 + timedelta(seconds=8)).isoformat(), "duration_s": round(random.uniform(4, 14), 1), "ttft_s": round(random.uniform(0.8, 6), 1),
                       "response": text, "finish_reason": "stop", "n_chunks": len(text) // 6, "http_status": 200, "error_shown": None, "request_id": f"demo-{mk}-{p}-{q['id']}",
                       "returned_model": [], "unknown_fields": [], "attempts": 1, "status": "ok"}
                if kind == "retry":
                    bad = dict(rec, status="timeout", response="", finish_reason=None, http_status=None, ttft_s=None, attempts=1)
                    lines.append(bad)
                    rec["attempts"] = 2
                lines.append(rec)
                if kind == "unmarked_link":
                    decisions.append({"dir": f"runs/{mk}", "profile": p, "id": q["id"], "response_sha256": hashlib.sha256(text.encode()).hexdigest(),
                                      "decided_status": "Ok - partial", "note": "Demo: a bare URL is not a cited source marker; keep the rule."})
            with open(os.path.join(d, f"{p}.jsonl"), "w") as f:
                f.write("\n".join(json.dumps(r) for r in lines) + "\n")
    json.dump(decisions, open(os.path.join(HERE, "validated_conflicts.json"), "w"), indent=1)
    print("demo dataset written:", HERE)


if __name__ == "__main__":
    main()
