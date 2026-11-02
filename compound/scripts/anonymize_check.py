#!/usr/bin/env python3
"""Generic leak scanner for a repo that is derived from a confidential engagement. Exit code 1 if anything is found.

Usage: python3 compound/scripts/anonymize_check.py [root]
       HARNESS_FORBIDDEN_FILE=~/.config/rag-harness/forbidden-terms.local python3 compound/scripts/anonymize_check.py

Two layers:
  1. GENERIC patterns, always on (committed here, safe to publish): API keys / tokens, private-key blocks, UUIDs,
     e-mail addresses, absolute home paths, internal-looking hostnames, .env files.
  2. PRIVATE terms, optional: one term per line (case-insensitive WHOLE-WORD match, so "acme" does not hit "acmeconf"; prefix a line with
     "~" for a raw substring match; lines starting with # ignored) read from the file named by
     HARNESS_FORBIDDEN_FILE. That file lives OUTSIDE the repo and is never committed: a committed list of client names would itself
     be the leak. In CI only layer 1 runs; run layer 2 locally before every push.

Allowlist: example.org / example.com hostnames, GitHub noreply and Anthropic noreply addresses (commit identity and trailers), and UUID-shaped strings on a line that carries the token `ALLOW-UUID`.
The scan also covers the file NAMES and (with --history) every patch, author and committer line in git history.
"""
import os
import re
import subprocess
import sys

GENERIC = {
    "api key / token": re.compile(r"(sk-[A-Za-z0-9_\-]{20,}|gh[pousr]_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_\-]{30,}|xox[baprs]-[A-Za-z0-9\-]{10,}|Bearer\s+[A-Za-z0-9._\-]{30,})"),
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "uuid": re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I),
    "e-mail": re.compile(r"\b[A-Za-z0-9._%+\-]+@(?!(?:example\.(?:com|org)|users\.noreply\.github\.com|anthropic\.com)\b)[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
    "home path": re.compile(r"(/Users/[A-Za-z0-9._\-]+|/home/[A-Za-z0-9._\-]+|C:\\Users\\[A-Za-z0-9._\-]+)"),
    "internal host": re.compile(r"https?://[A-Za-z0-9.\-]*(?:internal|intra|corp|prd|prod|staging)[A-Za-z0-9.\-]*\.[a-z]{2,}", re.I),
}
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache"}
SKIP_FILES = {"package-lock.json"}


def private_terms():
    p = os.environ.get("HARNESS_FORBIDDEN_FILE")
    if not p:
        return []
    p = os.path.expanduser(p)
    if not os.path.exists(p):
        sys.exit(f"HARNESS_FORBIDDEN_FILE set but missing: {p}")
    out = []
    for line in open(p, encoding="utf8"):
        t = line.strip()
        if not t or t.startswith("#"):
            continue
        raw = t.startswith("~")
        body = re.escape(t[1:] if raw else t)
        out.append(re.compile(body if raw else r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])", re.I))
    return out


def mask(s):
    """Never echo a secret: keep 4 characters of context only."""
    return s[:4] + "…[masked]"


def scan_text(label, text, terms, hits):
    for i, t in enumerate(terms, 1):
        if t.search(text):
            hits.append(f"{label}: private term (#{i} of the private list)")   # never echo the term itself
    for name, rx in GENERIC.items():
        for m in rx.finditer(text):
            line = text[text.rfind("\n", 0, m.start()) + 1: (text.find("\n", m.end()) if text.find("\n", m.end()) >= 0 else len(text))]
            if name == "uuid" and "ALLOW-UUID" in line:   # allowance is per line, never per file
                continue
            shown = mask(m.group(0)) if name in ("api key / token", "private key block") else m.group(0)[:60]
            hits.append(f"{label}: {name}: {shown}")


def candidate_files(root):
    """What WOULD be published: tracked + untracked-but-not-ignored files when root is a git repo, else every file under root."""
    if os.path.exists(os.path.join(root, ".git")):   # a directory, or a file for worktrees
        r = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard", "-z"], capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"git ls-files failed ({r.stderr.strip()[:120]}): refusing to report 'clean' on an unknown file list")
        return [x for x in r.stdout.split("\0") if x]
    return [os.path.relpath(os.path.join(d, f), root) for d, dirs, files in os.walk(root) if not dirs.__setitem__(slice(None), [x for x in dirs if x not in SKIP_DIRS]) for f in files]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    root = os.path.abspath(args[0] if args else ".")
    terms, hits = private_terms(), []
    for rel in candidate_files(root):
        path = os.path.join(root, rel)
        f = os.path.basename(rel)
        if f in SKIP_FILES or not os.path.isfile(path):
            continue
        if f == ".env" or (f.startswith(".env.") and f != ".env.example"):
            hits.append(f"{rel}: env file must not be in the repo")
            continue
        scan_text(rel + " (name)", rel, terms, hits)
        try:
            text = open(path, encoding="utf8").read()
        except (UnicodeDecodeError, OSError):
            continue   # binary: build artifacts are git-ignored; see docs/anonymization.md
        scan_text(rel, text, terms, hits)
    if "--history" in sys.argv and os.path.exists(os.path.join(root, ".git")):
        r = subprocess.run(["git", "-C", root, "log", "-p", "--all", "--no-color", "--format=fuller"], capture_output=True, text=True)   # fuller: author and committer lines are scanned too
        if r.returncode and "does not have any commits" not in r.stderr:
            sys.exit(f"git log failed ({r.stderr.strip()[:120]}): refusing to report 'clean'")
        scan_text("git history", r.stdout, terms, hits)
    for h in hits:
        print("LEAK:", h)
    print("scan:", "clean" if not hits else f"{len(hits)} finding(s)", f"(private list: {len(terms)} term(s))" if terms else "(generic layer only)")
    sys.exit(1 if hits else 0)


if __name__ == "__main__":
    main()
