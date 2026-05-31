
from dataclasses import dataclass, field
from typing import Callable
from urllib.error import HTTPError, URLError


@dataclass
class JobMatch:
    title: str
    company: str
    source: str
    remote_policy: str
    freshness: str
    fit: str
    score: int
    url: str
    details_text: str
    matched_keywords: str
    missing_skills: str
    fit_notes: str


@dataclass(frozen=True)
class DiscoveryContext:
    profile: str
    owned_skills: set[str]
    search_terms: list[str]
    cv_words: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class SourceAdapter:
    key: str
    label: str
    collector: Callable[[DiscoveryContext], list[JobMatch]]


@dataclass
class SourceRunReport:
    key: str
    label: str
    collected: int
    error: str = ""


@dataclass
class CollectionReport:
    sources: list[SourceRunReport]
    raw_total: int
    filtered_age: int
    filtered_score: int
    filtered_stretch: int
    filtered_salary: int
    filtered_timezone: int
    filtered_seniority: int
    dedup_collisions: int
    deduped_total: int


@dataclass
class ApiUpsertFailure:
    company: str
    title: str
    source: str
    status_code: int | None
    error_type: str
    message: str


@dataclass
class OutcomePriors:
    source: dict[str, float]
    role_family: dict[str, float]


TRANSIENT_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}


def classify_upsert_exception(exc: Exception) -> tuple[int | None, str, bool]:
    if isinstance(exc, HTTPError):
        status_code = int(getattr(exc, "code", 0) or 0)
        transient = status_code in TRANSIENT_HTTP_CODES
        return status_code, "HTTPError", transient
    if isinstance(exc, URLError):
        return None, "URLError", True
    if isinstance(exc, TimeoutError):
        return None, "TimeoutError", True
    return None, type(exc).__name__, False
