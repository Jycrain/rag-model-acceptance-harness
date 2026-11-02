#!/usr/bin/env python3
"""Compares blind reviewer verdicts with the pipeline statuses. Exit code 1 if a canary is missed.

Usage: python3 src/audit_consensus.py audit/key.json audit/reviewer-1.json [audit/reviewer-2.json ...]
                                      [--pack audit/pack.json] [--objections audit/objections.json]
Reviewer file: {"<case id>": {"has_source": true|false, "complete_answer": true|false, "quotes": ["<verbatim excerpt>", ...]}, ...}
  "quotes" is optional but, with --pack, every quote must be a LITERAL substring of the answer shown to the reviewer;
  a paraphrased or invented quote means the reviewer did not read: exit code 1.
Objections file (optional, written by an adversary pass): {"<case id>": "<why the consensus may be wrong>"}.
  A case with an objection never counts as agreement and is listed for human arbitration; exit code 1 if any.
  Objections on canaries are ignored on purpose: a canary is judged against its known expected verdict only.
A case is a DISAGREEMENT when the reviewer majority differs from the pipeline status
(Ok <=> has_source and complete_answer). Disagreements are listed for human arbitration: they may reveal a rule gap
(e.g. "announcement" answers that promise a search and deliver nothing: complete by the rule, empty for a human).
A missed canary means the reviewers did not really read: the audit is void, rerun it.
"""
import argparse
import json
import sys


def verdict(v):
    return "Ok" if v["has_source"] and v["complete_answer"] else ("Ko" if not v["complete_answer"] else "Ok - partial")


def literal_quote_errors(reviews, pack):
    """Returns [(reviewer index, case, quote)] for quotes that are not verbatim substrings of the answer."""
    answers = {c["case"]: c["answer"] for c in pack["cases"]}
    bad = []
    for n, r in enumerate(reviews, 1):
        for case, v in r.items():
            for q in v.get("quotes", []):
                if case not in answers or q not in answers[case]:
                    bad.append((n, case, q[:60]))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key")
    ap.add_argument("reviewers", nargs="+")
    ap.add_argument("--pack")
    ap.add_argument("--objections")
    a = ap.parse_args()
    key = json.load(open(a.key, encoding="utf8"))
    reviews = [json.load(open(p, encoding="utf8")) for p in a.reviewers]
    objections = json.load(open(a.objections, encoding="utf8")) if a.objections else {}
    bad = literal_quote_errors(reviews, json.load(open(a.pack, encoding="utf8"))) if a.pack else []
    for n, case, q in bad:
        print(f"NON-LITERAL QUOTE: reviewer {n}, {case}: {q!r}")
    agree = disagree = missed = objected = 0
    for case, k in key.items():
        votes = [verdict(r[case]) for r in reviews if case in r]
        if not votes:
            print("NOT REVIEWED:", case)
            continue
        top = max(votes.count(v) for v in set(votes))
        leaders = sorted(v for v in set(votes) if votes.count(v) == top)
        majority = leaders[0] if len(leaders) == 1 else None   # a tie is never a majority: it is a disagreement
        if case in objections and not k["canary"]:
            objected += 1
            print("OBJECTION:", case, "-", objections[case])
        elif majority == k["pipeline_status"]:
            agree += 1
        else:
            disagree += 1
            if k["canary"]:
                missed += 1
                print("CANARY MISSED:", case, "-", k["canary"])
            else:
                print("DISAGREEMENT:", case, f"pipeline={k['pipeline_status']} reviewers={votes}")
    print(f"agree {agree}, disagree {disagree}, objections {objected}, canaries missed {missed}, non-literal quotes {len(bad)}")
    sys.exit(1 if (missed or bad or objected) else 0)


if __name__ == "__main__":
    main()
