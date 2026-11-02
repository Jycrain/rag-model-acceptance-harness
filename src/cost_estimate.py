#!/usr/bin/env python3
"""Cost estimate per series with a LOW / CENTRAL / HIGH range, every assumption explicit and traceable.

Usage: python3 src/cost_estimate.py --config examples/demo/config.json [--measured measured.json] [--out cost.json]

Why an estimate: the RAG back end may return NO token usage (probe it with src/probe_usage.js). Then cost = requests x tokens x price
cannot be measured from the logs. Only what the logs DO contain is used as a fact (number of requests incl. retries, answer length);
the rest is an assumption with a range.

Per request (scenario s in low / central / high):
  input_tokens  = question_chars / chars_per_token + rag_context_tokens[s]          (retrieved passages dominate and are NOT in the logs)
  output_tokens = (answer_chars / chars_per_token) x reasoning_multiplier[model][s]  (hidden reasoning tokens are billed as output)
  calls         = intermediate_call_factor[s]                                        (query rewriting, routing, re-ranking: unknown)
  cost          = calls x (input_tokens x price_in + output_tokens x price_out) / 1e6 x price_factor[s]
Failed attempts (retries, timeouts) are counted as requests: they may be billed.

If the platform / provider console gives real token totals per model and time window, pass them with --measured:
  {"<series>": {"input_tokens": N, "output_tokens": N}}  -> that series gets an exact-token cost (price uncertainty only).

Prices come from the config ("prices_per_mtok": {model: {input, output, currency, source, date}}). Never invent a price: cite its
source and date, and prefer the provider's own page over aggregators (docs/cost-estimation.md lists the pitfalls).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import load

SCENARIOS = ("low", "central", "high")
DEFAULT_MODEL = {
    "chars_per_token": 3.5,   # prose, BPE tokenizers: roughly 3.2-4.2 chars per token
    "rag_context_tokens": {"low": 2000, "central": 6000, "high": 15000},
    "intermediate_call_factor": {"low": 1.0, "central": 1.0, "high": 2.0},
    "price_factor": {"low": 0.8, "central": 1.0, "high": 1.3},   # list price uncertainty / currency / tier change
    "reasoning_multiplier": {"low": 1.0, "central": 1.0, "high": 1.0},
}


def merge(base, over):
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in (over or {}).items():
        out[k] = {**out.get(k, {}), **v} if isinstance(v, dict) else v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.environ.get("HARNESS_CONFIG"))
    ap.add_argument("--measured")
    ap.add_argument("--out", default="cost.json")
    a = ap.parse_args()
    cfg = load(a.config)
    base = cfg["_dir"]
    prices = cfg.get("prices_per_mtok", {})
    measured = json.load(open(a.measured, encoding="utf8")) if a.measured else {}
    result = {}
    for name, spec in cfg["series"].items():
        model = spec["model"]
        if model not in prices:
            print(f"SKIP {name}: no price for model {model} in config")
            continue
        P = prices[model]
        A = merge(DEFAULT_MODEL, cfg.get("cost_assumptions", {}).get("default"))
        A = merge(A, cfg.get("cost_assumptions", {}).get(model))
        n_req, q_chars, a_chars = 0, 0, 0
        for p in cfg["profiles"]:
            for line in open(os.path.join(base, spec["dir"], p + ".jsonl"), encoding="utf8"):
                r = json.loads(line)
                n_req += 1
                q_chars += len(r["question"])
                a_chars += len(r.get("response") or "")
        row = {"currency": P["currency"], "price_source": P.get("source"), "price_date": P.get("date"), "requests": n_req, "question_chars": q_chars, "answer_chars": a_chars, "scenarios": {}}
        for s in SCENARIOS:
            if name in measured:
                tin, tout, calls = measured[name]["input_tokens"], measured[name]["output_tokens"], 1.0
                basis = "measured tokens"
            else:
                tin = (q_chars / A["chars_per_token"] + n_req * A["rag_context_tokens"][s])
                tout = a_chars / A["chars_per_token"] * A["reasoning_multiplier"][s]
                calls, basis = A["intermediate_call_factor"][s], "assumed tokens"
            cost = calls * (tin * P["input"] + tout * P["output"]) / 1e6 * A["price_factor"][s]
            row["scenarios"][s] = {"input_tokens": round(tin * calls), "output_tokens": round(tout * calls), "cost": round(cost, 4), "basis": basis}
        result[name] = row
        c = row["scenarios"]
        print(f"{name:12s} {n_req:4d} requests  {c['low']['cost']:.3f} / {c['central']['cost']:.3f} / {c['high']['cost']:.3f} {P['currency']} (low / central / high)")
    tot = {s: round(sum(r["scenarios"][s]["cost"] for r in result.values()), 4) for s in SCENARIOS}
    result["_total"] = tot
    print("TOTAL", tot)
    json.dump(result, open(os.path.join(base, a.out), "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
