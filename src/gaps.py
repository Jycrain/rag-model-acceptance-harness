"""Indicative "gap signalled" heuristic: the answer says it does not cover / does not specify something.

Keyword based and English only: extend the pattern for your language. It NEVER takes part in the Ok / Ok - partial / Ko statuses
(see status.py): it is a reading aid for reviewers, nothing more.
"""
import re

GAP = re.compile(
    r"(do(es)? not (cover|contain|specify|mention|provide)|no (document|information|record) (found|available)"
    r"|(is|are) not (available|documented|specified)|unable to find|cannot be determined"
    r")",
    re.I,
)
