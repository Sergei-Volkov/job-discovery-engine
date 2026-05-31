"""Backward-compatible re-export hub for the discovery package.

The discovery logic was previously a single monolith in this file.
It has been split into focused sub-modules:

  models.py      — dataclasses (JobMatch, SourceAdapter, CollectionReport, …)
  config.py      — constants, feed URLs, keyword weights, patterns, mutable globals
  text_utils.py  — HTTP helpers (fetch_json/text/post_json) + text/date utilities
  scoring.py     — scoring, relevance, CV extraction, seniority, salary, priors

This file re-exports every public name so that existing callers
(cli.py, sources.py, outputs.py) continue to work without modification.
"""

# ---- dataclasses + exception classifier ------------------------------------
try:
    from .models import (
        ApiUpsertFailure,
        CollectionReport,
        DiscoveryContext,
        JobMatch,
        OutcomePriors,
        SourceAdapter,
        SourceRunReport,
        TRANSIENT_HTTP_CODES,
        classify_upsert_exception,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from models import (
        ApiUpsertFailure,
        CollectionReport,
        DiscoveryContext,
        JobMatch,
        OutcomePriors,
        SourceAdapter,
        SourceRunReport,
        TRANSIENT_HTTP_CODES,
        classify_upsert_exception,
    )

# ---- constants + mutable globals -------------------------------------------
try:
    from .config import (
        ACTIVE_PROFILE,
        ARBEITNOW_API,
        DEFAULT_API_BASE_URL,
        DEFAULT_API_WRITE_KEY,
        DISPLAY_NAMES,
        JOBICY_FEED,
        KEYWORD_WEIGHTS,
        OWNED_SKILLS,
        PROFILE_SEARCH_TERMS,
        REJECT_PATTERNS,
        REMOTEOK_API,
        REMOTIVE_API,
        SCORE_MEDIUM_MIN,
        SCORE_STRONG_MIN,
        SEARCH_TERMS,
        SENIORITY_LEVELS,
        SKILL_PATTERNS,
        SOURCE_OPTIONS,
        WORKING_NOMADS_API,
        WWR_FEEDS,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from config import (
        ACTIVE_PROFILE,
        ARBEITNOW_API,
        DEFAULT_API_BASE_URL,
        DEFAULT_API_WRITE_KEY,
        DISPLAY_NAMES,
        JOBICY_FEED,
        KEYWORD_WEIGHTS,
        OWNED_SKILLS,
        PROFILE_SEARCH_TERMS,
        REJECT_PATTERNS,
        REMOTEOK_API,
        REMOTIVE_API,
        SCORE_MEDIUM_MIN,
        SCORE_STRONG_MIN,
        SEARCH_TERMS,
        SENIORITY_LEVELS,
        SKILL_PATTERNS,
        SOURCE_OPTIONS,
        WORKING_NOMADS_API,
        WWR_FEEDS,
    )

# ---- HTTP helpers -----------------------------------------------------------
try:
    from .text_utils import fetch_json, fetch_text, post_json
except ImportError:  # pragma: no cover - script-mode fallback
    from text_utils import fetch_json, fetch_text, post_json

# ---- text / date utilities -------------------------------------------------
try:
    from .text_utils import (
        normalize,
        normalize_url,
        parse_date,
        parse_remote_policy,
        read_cv_text,
        split_company_and_title,
        strip_latex,
        days_old,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from text_utils import (
        normalize,
        normalize_url,
        parse_date,
        parse_remote_policy,
        read_cv_text,
        split_company_and_title,
        strip_latex,
        days_old,
    )

# ---- scoring and filtering -------------------------------------------------
try:
    from .scoring import (
        apply_outcome_priors,
        build_fit_note,
        build_job_match,
        build_outcome_priors,
        classify_role_family,
        cv_word_bag,
        extract_keywords,
        extract_owned_skills_from_cv,
        extract_salary_ceiling_usd,
        fit_label,
        infer_search_terms_for_profile,
        infer_seniority,
        is_relevant,
        matches_salary_requirement,
        matches_seniority,
        matches_timezone,
        next_step_for_fit,
        profile_reject_patterns,
        profile_title_signals,
        score_match,
        status_outcome_weight,
        tailoring_points,
    )
except ImportError:  # pragma: no cover - script-mode fallback
    from scoring import (
        apply_outcome_priors,
        build_fit_note,
        build_job_match,
        build_outcome_priors,
        classify_role_family,
        cv_word_bag,
        extract_keywords,
        extract_owned_skills_from_cv,
        extract_salary_ceiling_usd,
        fit_label,
        infer_search_terms_for_profile,
        infer_seniority,
        is_relevant,
        matches_salary_requirement,
        matches_seniority,
        matches_timezone,
        next_step_for_fit,
        profile_reject_patterns,
        profile_title_signals,
        score_match,
        status_outcome_weight,
        tailoring_points,
    )

__all__ = [
    # models
    "ApiUpsertFailure", "CollectionReport", "DiscoveryContext", "JobMatch", "OutcomePriors",
    "SourceAdapter", "SourceRunReport", "TRANSIENT_HTTP_CODES",
    "classify_upsert_exception",
    # config constants
    "ACTIVE_PROFILE", "ARBEITNOW_API", "DEFAULT_API_BASE_URL", "DEFAULT_API_WRITE_KEY",
    "DISPLAY_NAMES", "JOBICY_FEED", "KEYWORD_WEIGHTS", "OWNED_SKILLS",
    "PROFILE_SEARCH_TERMS", "REJECT_PATTERNS", "REMOTEOK_API", "REMOTIVE_API",
    "SCORE_MEDIUM_MIN", "SCORE_STRONG_MIN", "SEARCH_TERMS", "SENIORITY_LEVELS",
    "SKILL_PATTERNS", "SOURCE_OPTIONS", "WORKING_NOMADS_API", "WWR_FEEDS",
    # HTTP helpers
    "fetch_json", "fetch_text", "post_json",
    # text / date utils
    "normalize", "normalize_url", "parse_date", "parse_remote_policy",
    "split_company_and_title", "strip_latex", "days_old",
    # scoring / filtering
    "apply_outcome_priors", "build_fit_note", "build_job_match",
    "build_outcome_priors", "classify_role_family", "extract_keywords",
    "extract_owned_skills_from_cv", "extract_salary_ceiling_usd", "fit_label",
    "infer_search_terms_for_profile", "infer_seniority", "is_relevant",
    "matches_salary_requirement", "matches_seniority", "matches_timezone",
    "next_step_for_fit", "profile_reject_patterns", "profile_title_signals",
    "score_match", "status_outcome_weight", "tailoring_points",
]
