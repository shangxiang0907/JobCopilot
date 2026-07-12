"""Shared types and helpers for source adapters."""

import html
import re
from dataclasses import dataclass, field

USER_AGENT = "JobCopilot/0.2 (+https://github.com/shangxiang0907/JobCopilot)"

# Each source contributes at most this many jobs per run — keeps a single run
# bounded no matter how large the upstream feed is.
PER_SOURCE_LIMIT = 50

# Downstream LLM analysis caps its input anyway; don't ship megabytes around.
RAW_TEXT_LIMIT = 8000

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"[ \t]{2,}")


@dataclass
class SearchCriteria:
    keywords: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    job_types: list[str] = field(default_factory=list)
    salary_min: int | None = None


@dataclass
class RawJob:
    url: str
    title: str
    company_name: str
    location: str = ""
    posted_snippet: str = ""
    raw_text: str = ""
    source: str = ""


def strip_html(text: str) -> str:
    """Plain-text-ify an HTML fragment (tags out, entities unescaped).

    Opening AND closing block-level tags become newlines — HN comments, for
    one, separate paragraphs with bare `<p>` and never close them.
    """
    text = re.sub(r"</?(p|div|li|br|h[1-6])(\s[^>]*)?/?>", "\n", text, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WS_RE.sub(" ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())[:RAW_TEXT_LIMIT]


def matches_keywords(criteria: SearchCriteria, *haystacks: str) -> bool:
    """Lenient keyword filter: no keywords → everything matches; otherwise any
    keyword must appear in any provided text (case-insensitive)."""
    if not criteria.keywords:
        return True
    combined = " ".join(h.lower() for h in haystacks if h)
    return any(kw.lower() in combined for kw in criteria.keywords if kw.strip())


def matches_location(criteria: SearchCriteria, job_location: str) -> bool:
    """Lenient location filter: no requested locations, or the job has no
    location data → match; otherwise substring match either direction (job
    boards write locations inconsistently: "Remote - Europe" vs "europe")."""
    if not criteria.locations or not job_location:
        return True
    job_loc = job_location.lower()
    for wanted in criteria.locations:
        w = wanted.strip().lower()
        if w and (w in job_loc or job_loc in w):
            return True
    return False
