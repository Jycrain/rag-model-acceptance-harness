"""Shared configuration loader. A run is described by one JSON file (see config.example.json).

The path comes from the HARNESS_CONFIG environment variable or from an explicit argument. Every
setting has a default so that the status rule can be unit-tested without any file.

Citation convention (what counts as a "cited source" in an answer) is declared once, in the config, as a preset:
  {"citation": {"preset": "bracket_id"}}                      [src: kb-0427-handbook]       (default, easiest to request in a system prompt)
  {"citation": {"preset": "bracket_number"}}                  [3]
  {"citation": {"preset": "markdown_link"}}                   [Handbook](https://docs.example.net/handbook)
  {"citation": {"preset": "bold_prefixed", "prefixes": ["DOC_\\d+_"], "canary_marker": "**DOC_4821_notes.txt**"}}
                                                              **DOC_12_guide.txt**   (bold text starting with a known id prefix; regex fragments)
  {"citation": {"preset": "custom", "source_pattern": "...", "suspect_pattern": "...", "canary_marker": "..."}}
`source_pattern` must contain one capture group (the source id). `source_marker_start_pattern` is a second, independent way
to count markers (used by compare.py as a cross-check); presets provide it, for "custom" it defaults to `source_pattern`. `suspect_pattern` is a broad detector that never classifies,
it only raises a conflict when an answer ranked "partial" still looks like it cites something. `canary_marker` is a plausible
marker injected by audit_prepare.py into canary answers. Legacy top-level `source_pattern` / `suspect_pattern` keys still work.
"""
import json
import os

_GENERIC_SUSPECT = r"https?://|\[\d+\]|\[src\b|\.(?:pdf|txt|md|docx?)\b"

PRESETS = {
    "bracket_id": {
        "source_pattern": r"\[src:\s*([^\]\n]+?)\s*\]",
        "suspect_pattern": _GENERIC_SUSPECT,
        "canary_marker": "[src: kb-0427-handbook]",
        "source_marker_start_pattern": r"\[src:",
    },
    "bracket_number": {
        "source_pattern": r"\[(\d{1,3})\]",
        "suspect_pattern": _GENERIC_SUSPECT,
        "canary_marker": "[7]",
        "source_marker_start_pattern": r"\[\d{1,3}\]",
    },
    "markdown_link": {
        "source_pattern": r"\[[^\]\n]+\]\((https?://[^)\s]+)\)",
        "suspect_pattern": r"https?://|\.(?:pdf|txt|md|docx?)\b",
        "canary_marker": "[Handbook](https://docs.example.net/handbook)",
        "source_marker_start_pattern": r"\]\(https?://",
    },
}


def resolve_citation(citation):
    """Returns {source_pattern, suspect_pattern, canary_marker} for a `citation` block (see module docstring)."""
    c = dict(citation or {})
    preset = c.get("preset", "bracket_id")
    if preset in PRESETS:
        out = dict(PRESETS[preset])
    elif preset == "bold_prefixed":
        prefixes = c.get("prefixes")
        if not prefixes:
            raise ValueError('citation preset "bold_prefixed" needs "prefixes" (list of regex fragments)')
        out = {"source_pattern": r"\*\*((?:%s)[^*]+)\*\*" % "|".join(prefixes), "suspect_pattern": _GENERIC_SUSPECT, "canary_marker": None,
               "source_marker_start_pattern": r"\*\*(?:%s)" % "|".join(prefixes)}
    elif preset == "custom":
        if "source_pattern" not in c:
            raise ValueError('citation preset "custom" needs "source_pattern"')
        out = {"source_pattern": c["source_pattern"], "suspect_pattern": _GENERIC_SUSPECT, "canary_marker": None,
               "source_marker_start_pattern": c.get("source_marker_start_pattern", c["source_pattern"])}
    else:
        raise ValueError(f"unknown citation preset: {preset} (expected {', '.join(list(PRESETS) + ['bold_prefixed', 'custom'])})")
    for k in ("source_pattern", "suspect_pattern", "canary_marker", "source_marker_start_pattern"):
        if c.get(k):
            out[k] = c[k]
    return out


DEFAULTS = {
    "citation": {"preset": "bracket_id"},
    **resolve_citation({"preset": "bracket_id"}),
    "api": {"type": "openai_chat_sse", "route": "/v1/chat/completions"},
    "questions": "questions.json",
    "profiles": {},
    "series": {},
    "models": {},
}


_LAST = None


def load(path=None):
    """Return DEFAULTS merged with the JSON file at `path` (or $HARNESS_CONFIG). Missing file -> defaults."""
    global _LAST
    if _LAST and not os.path.exists(_LAST):
        _LAST = None   # a remembered config that no longer exists (temporary directory) must not shadow $HARNESS_CONFIG
    path = path or _LAST or os.environ.get("HARNESS_CONFIG") or None
    if path and not os.path.exists(path):
        raise FileNotFoundError(f"config file not found: {path}")
    if path:
        _LAST = path   # later load() calls without argument (e.g. in conflicts.py) reuse the explicit path
    cfg = dict(DEFAULTS)
    if path and os.path.exists(path):
        with open(path, encoding="utf8") as f:
            user = json.load(f)
        cfg.update(user)
        if "citation" in user or "source_pattern" in user or "suspect_pattern" in user:
            citation = dict(user.get("citation") or {})
            if "citation" not in user:   # legacy keys only: treat them as a custom convention
                citation = {"preset": "custom", "source_pattern": user.get("source_pattern", DEFAULTS["source_pattern"])}
                if "suspect_pattern" in user:
                    citation["suspect_pattern"] = user["suspect_pattern"]
                if "canary_marker" in user:
                    citation["canary_marker"] = user["canary_marker"]
                if "source_marker_start_pattern" in user:
                    citation["source_marker_start_pattern"] = user["source_marker_start_pattern"]
            cfg.update(resolve_citation(citation))
        cfg["_dir"] = os.path.dirname(os.path.abspath(path))
    else:
        cfg["_dir"] = os.getcwd()
    return cfg
