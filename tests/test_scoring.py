import sys
from pathlib import Path

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import pytest
from job_discovery_engine.models import DiscoveryContext
from job_discovery_engine.scoring import (
    build_fit_note,
    extract_keywords,
    extract_salary_ceiling_usd,
    fit_label,
    infer_seniority,
    is_relevant,
    matches_salary_requirement,
    matches_seniority,
    matches_timezone,
    score_match,
)
from job_discovery_engine import config as discovery_config


# ── score_match ───────────────────────────────────────────────────────────────


def test_score_match_owned_skills_boost_score() -> None:
    ctx_owned = DiscoveryContext(profile="de", owned_skills={"python", "sql"}, search_terms=[])
    ctx_none = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    score_with = score_match("Data Engineer", "python sql pipeline", context=ctx_owned)
    score_without = score_match("Data Engineer", "python sql pipeline", context=ctx_none)
    assert score_with > score_without


def test_score_match_data_engineer_title_bonus() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    with_title = score_match("Data Engineer", "", context=ctx)
    without_title = score_match("Software Developer", "", context=ctx)
    # "data engineer" in title gives +6
    assert with_title - without_title == 6


def test_score_match_swe_title_bonus() -> None:
    ctx = DiscoveryContext(profile="swe", owned_skills=set(), search_terms=[])
    with_title = score_match("Software Engineer", "", context=ctx)
    without_title = score_match("Data Scientist", "", context=ctx)
    assert with_title - without_title == 5


def test_score_match_sre_site_reliability_bonus() -> None:
    ctx = DiscoveryContext(profile="sre", owned_skills=set(), search_terms=[])
    with_title = score_match("Site Reliability Engineer", "", context=ctx)
    without_title = score_match("Accountant", "", context=ctx)
    assert with_title - without_title == 6


def test_score_match_remote_bonus() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    with_remote = score_match("Data Engineer", "remote work worldwide", context=ctx)
    without_remote = score_match("Data Engineer", "", context=ctx)
    assert with_remote > without_remote


# ── fit_label ─────────────────────────────────────────────────────────────────


def test_fit_label_strong() -> None:
    assert fit_label(discovery_config.SCORE_STRONG_MIN) == "Strong"
    assert fit_label(discovery_config.SCORE_STRONG_MIN + 5) == "Strong"


def test_fit_label_medium() -> None:
    assert fit_label(discovery_config.SCORE_MEDIUM_MIN) == "Medium"
    assert fit_label(discovery_config.SCORE_STRONG_MIN - 1) == "Medium"


def test_fit_label_stretch() -> None:
    assert fit_label(0) == "Stretch"
    assert fit_label(discovery_config.SCORE_MEDIUM_MIN - 1) == "Stretch"


# ── is_relevant ───────────────────────────────────────────────────────────────


def test_is_relevant_rejects_manager_title() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    assert not is_relevant("Data Engineering Manager", "", context=ctx)


def test_is_relevant_accepts_strong_title_signal() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    assert is_relevant("Data Engineer", "", context=ctx)


def test_is_relevant_swe_accepts_backend_engineer() -> None:
    ctx = DiscoveryContext(profile="swe", owned_skills=set(), search_terms=[])
    assert is_relevant("Backend Engineer", "", context=ctx)


def test_is_relevant_de_rejects_pure_backend_no_stack() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    assert not is_relevant("Backend Engineer", "React TypeScript mobile app", context=ctx)


def test_is_relevant_adjacent_title_with_enough_stack_keywords() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    # "devops" title + 3 stack keywords should match
    details = "airflow dbt databricks bigquery pipeline analytics"
    assert is_relevant("DevOps Engineer", details, context=ctx)


# ── extract_keywords ──────────────────────────────────────────────────────────


def test_extract_keywords_splits_owned_and_missing() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills={"python", "sql"}, search_terms=[])
    owned, missing = extract_keywords("python sql dbt airflow", context=ctx)
    assert "Python" in owned
    assert "SQL" in owned
    # dbt and airflow not in owned_skills
    assert any("dbt" in m.lower() for m in missing)
    assert any("airflow" in m.lower() for m in missing)


def test_extract_keywords_empty_text() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills={"python"}, search_terms=[])
    owned, missing = extract_keywords("", context=ctx)
    assert owned == []
    assert missing == []


# ── build_fit_note ────────────────────────────────────────────────────────────


def test_build_fit_note_returns_three_values() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills={"python", "sql"}, search_terms=[])
    matched, missing, note = build_fit_note("Data Engineer", "python sql dbt", "Remote", context=ctx)
    assert isinstance(matched, str)
    assert isinstance(missing, str)
    assert isinstance(note, str)
    assert len(note) > 0


def test_build_fit_note_includes_remote_mention() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills=set(), search_terms=[])
    _, _, note = build_fit_note("Data Engineer", "", "Remote", context=ctx)
    assert "remote" in note.lower() or "General overlap" in note


# ── extract_salary_ceiling_usd ────────────────────────────────────────────────


def test_extract_salary_ceiling_returns_none_for_no_salary_info() -> None:
    assert extract_salary_ceiling_usd("Join our fast-growing team") is None


def test_extract_salary_ceiling_parses_k_notation() -> None:
    result = extract_salary_ceiling_usd("Salary up to $120k USD per year")
    assert result == 120_000


def test_extract_salary_ceiling_parses_full_number() -> None:
    result = extract_salary_ceiling_usd("Compensation: up to 95000 USD")
    assert result == 95_000


def test_extract_salary_ceiling_picks_max_when_multiple() -> None:
    result = extract_salary_ceiling_usd("Range $80k to $140k USD")
    assert result == 140_000


# ── matches_salary_requirement ────────────────────────────────────────────────


def test_matches_salary_passes_when_no_min() -> None:
    assert matches_salary_requirement("Engineer", "salary 50k usd", minimum_usd=None)


def test_matches_salary_passes_when_ceiling_meets_min() -> None:
    assert matches_salary_requirement("Engineer", "up to $100k usd", minimum_usd=80_000)


def test_matches_salary_fails_when_ceiling_below_min() -> None:
    assert not matches_salary_requirement("Engineer", "up to $60k usd", minimum_usd=80_000)


def test_matches_salary_passes_when_no_salary_info() -> None:
    # No salary info — we assume it might be negotiable, so pass
    assert matches_salary_requirement("Engineer", "Join our team", minimum_usd=80_000)


# ── matches_timezone ──────────────────────────────────────────────────────────


def test_matches_timezone_passes_with_no_filter() -> None:
    assert matches_timezone("Remote", "work from anywhere", allowed_timezones=None)


def test_matches_timezone_passes_when_matching_tz_found() -> None:
    assert matches_timezone("Remote", "CET timezone preferred", allowed_timezones=["CET", "UTC"])


def test_matches_timezone_fails_when_no_match() -> None:
    assert not matches_timezone("US only", "EST timezone required only", allowed_timezones=["CET"])


def test_matches_timezone_passes_for_open_remote() -> None:
    assert matches_timezone("Remote", "work from anywhere", allowed_timezones=["CET"])


# ── infer_seniority / matches_seniority ───────────────────────────────────────


@pytest.mark.parametrize("title,expected", [
    ("Senior Data Engineer", "senior"),
    ("Junior Software Engineer", "junior"),
    ("Data Engineer", "mid"),
    ("Lead Platform Engineer", "lead"),
    ("Staff Engineer", "staff"),
    ("Principal Engineer", "staff"),
])
def test_infer_seniority(title: str, expected: str) -> None:
    from job_discovery_engine.scoring import infer_seniority
    assert infer_seniority(title, "") == expected


def test_matches_seniority_passes_when_no_filter() -> None:
    assert matches_seniority("Junior Engineer", "", requested=None)


def test_matches_seniority_senior_passes_for_senior_request() -> None:
    assert matches_seniority("Senior Data Engineer", "", requested="senior")


def test_matches_seniority_junior_fails_for_senior_request() -> None:
    assert not matches_seniority("Junior Data Engineer", "", requested="senior")


def test_matches_seniority_senior_passes_for_mid_request() -> None:
    # Senior >= mid, so it passes
    assert matches_seniority("Senior Data Engineer", "", requested="mid")
