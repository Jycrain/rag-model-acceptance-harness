# Anonymising a client engagement before publishing

Generalising work done for a client into something shareable is a procedure, not a find-and-replace. This is the one used to generalise this repo; it applies to any similar publication.

## Rule 0: the list of real terms never enters the repo

A committed list of client names, domains or agent ids *is* the leak, and git history keeps it forever. So:
- the real list lives in a **local file outside the repo** (for example `~/.config/rag-harness/forbidden-terms.local`);
- the scanner reads it through `HARNESS_FORBIDDEN_FILE`; findings never echo the matched term;
- CI runs only the generic layer; the private layer runs locally before every push (`--history` also scans git history);
- `compound/forbidden-terms.example` shows the format with fake terms.

## Categories to scrub (describe, never list real values here)

| Category | Examples of what to look for |
|---|---|
| Client and product identity | organisation, product, assistant, platform names and abbreviations |
| Network identity | domains, sub-domains, URLs, tenants, base URLs, agent/credential identifiers (UUIDs) |
| People | participants, client contacts, colleagues, employer-internal names |
| Engagement internals | budget, team structure, tensions, planning, who said what |
| Content | question text, answer text, source/document identifiers, extracts, screenshots, price captures taken from the client's tools |
| Secrets | keys, tokens, `.env` files, even partial tails |
| Machine traces | absolute home paths, session ids, tool caches (cost-tracking folders, editor state) |
| Derived fingerprints | hashes of client journals or question sets |

## Procedure

1. **New repository, new history.** Never push the engagement repo's history; `git init` and a single clean first commit.
2. **Copy file by file**, then rewrite: parameters instead of client constants (config + environment), neutral vocabulary
   (profiles A/B or member/visitor, "the platform"), English prose.
3. **Replace data with synthetic data** (`examples/demo/generate_demo.py`): a fictional domain, fabricated questions and
   answers that exercise every branch of the code.
4. **Aggregates only** for results, after the client or employer agreed to their publication. Public model names are fine;
   question and answer content is not.
5. **Generic scan** (`compound/scripts/anonymize_check.py`, also in CI and `tests/test_no_leak.py`).
6. **Private scan** with the real list, plus `--history`.
7. **Blind read**: a reviewer without any context about the client reads the whole repo and reports anything that could
   identify the client, the people or the engagement. Do not send client text to external services for this.
8. **Authorisation.** Confirm with the client and your employer that publishing the method and the aggregates is acceptable.
   Publishing is irreversible (caches, forks, indexes).
9. Create the repo **private** first; switch to public only after steps 5-8.

## Scanner scope

It scans what *would be published* (`git ls-files -co --exclude-standard`), so git-ignored caches and run folders are not
reported but also never leave. Binary files are not scanned: do not commit generated workbooks or decks from real data
(`.gitignore` excludes `*.xlsx`, `*.pptx`, `runs/`).
