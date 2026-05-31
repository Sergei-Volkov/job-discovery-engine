
import json
import sys
from dataclasses import fields
from pathlib import Path
from unittest.mock import MagicMock

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(_SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(_SRC_ROOT))

import job_discovery_engine as discovery_package  # noqa: E402
from job_discovery_engine import api as discovery_api  # noqa: E402
from job_discovery_engine import config as discovery_config  # noqa: E402
from job_discovery_engine.config import USER_CONFIG_PATH, _deep_merge, _load_discovery_config  # noqa: E402
from job_discovery_engine.models import CollectionReport, DiscoveryContext, JobMatch, SourceRunReport  # noqa: E402
from job_discovery_engine.pipeline import DiscoveryRunOptions, run_discovery_pipeline  # noqa: E402
from job_discovery_engine.rerankers import LLMRerankReport  # noqa: E402
from job_discovery_engine.scoring import cv_word_bag, is_relevant, score_match  # noqa: E402
from job_discovery_engine.sources import collect_remotive  # noqa: E402
from job_discovery_engine.text_utils import read_cv_text  # noqa: E402


def test_public_api_surface_is_frozen() -> None:
    assert discovery_package.__all__ == [
        "DiscoveryContext",
        "DiscoveryRunOptions",
        "DiscoveryRunResult",
        "DiscoveryRunWarnings",
        "run_discovery_pipeline",
    ]
    assert discovery_api.__all__ == [
        "DiscoveryRunOptions",
        "DiscoveryRunResult",
        "DiscoveryRunWarnings",
        "run_discovery_pipeline",
    ]


def test_public_dataclass_shapes_are_stable() -> None:
    assert [field.name for field in fields(DiscoveryContext)] == ["profile", "owned_skills", "search_terms", "cv_words"]
    assert [field.name for field in fields(DiscoveryRunOptions)] == [
        "cv_path",
        "limit",
        "min_score",
        "max_age_days",
        "include_stretch",
        "profile",
        "sources",
        "salary_min_usd",
        "timezones",
        "seniority",
        "use_outcome_priors",
        "prior_lookback_days",
        "source_prior_weight",
        "role_prior_weight",
        "use_llm_reranker",
        "llm_top_n",
        "llm_weight",
        "llm_model",
        "llm_api_base_url",
        "llm_dry_run",
        "llm_max_calls",
        "llm_max_input_chars",
        "llm_max_retries",
        "llm_retry_backoff_seconds",
        "llm_timeout_seconds",
        "api_base_url",
        "api_write_key",
        "output_dir",
    ]
    assert [field.name for field in fields(discovery_api.DiscoveryRunResult)] == [
        "context",
        "strict_matches",
        "broad_matches",
        "collection_report",
        "llm_report",
        "csv_path",
        "strict_md_path",
        "broad_md_path",
        "notes_path",
        "checklist_path",
        "synced_count",
        "failed_rows",
    ]


def _sample_match() -> JobMatch:
    return JobMatch(
        title="Backend Engineer",
        company="Acme",
        source="Remotive",
        remote_policy="Remote",
        freshness="2026-05-20",
        fit="Strong",
        score=14,
        url="https://example.com/jobs/1",
        details_text="Python SQL FastAPI",
        matched_keywords="Python, SQL",
        missing_skills="dbt",
        fit_notes="Direct overlap on Python and SQL.",
    )


def test_explicit_context_overrides_globals() -> None:
    original_profile = discovery_config.ACTIVE_PROFILE
    original_owned_skills = set(discovery_config.OWNED_SKILLS)
    try:
        discovery_config.ACTIVE_PROFILE = "de"
        discovery_config.OWNED_SKILLS.clear()

        swe_context = DiscoveryContext(profile="swe", owned_skills={"python"}, search_terms=["backend engineer"])
        de_context = DiscoveryContext(profile="de", owned_skills={"python"}, search_terms=["data engineer"])

        assert is_relevant("Backend Engineer", "", context=swe_context)
        assert not is_relevant("Backend Engineer", "", context=de_context)

        context_score = score_match(
            "Data Engineer",
            "Python SQL",
            context=DiscoveryContext(
                profile="de",
                owned_skills={"python"},
                search_terms=[],
            ),
        )
        fallback_score = score_match("Data Engineer", "Python SQL")

        assert context_score > fallback_score
    finally:
        discovery_config.ACTIVE_PROFILE = original_profile
        discovery_config.OWNED_SKILLS.clear()
        discovery_config.OWNED_SKILLS.update(original_owned_skills)


def test_collect_remotive_uses_context_search_terms(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch_text(url: str, timeout: int = 25) -> str:
        calls.append(url)
        return json.dumps(
            {
                "jobs": [
                    {
                        "title": "Backend Engineer",
                        "company_name": "Acme",
                        "description": "Python FastAPI SQL",
                        "candidate_required_location": "Remote",
                        "publication_date": "2026-05-20",
                        "url": "https://example.com/jobs/1",
                    }
                ]
            }
        )

    monkeypatch.setattr("job_discovery_engine.sources.fetch_text", fake_fetch_text)

    context = DiscoveryContext(
        profile="swe",
        owned_skills={"python"},
        search_terms=["backend engineer", "platform engineer"],
    )
    matches = collect_remotive(context)

    assert len(calls) == 2
    assert len(matches) == 1
    assert matches[0].company == "Acme"


def test_run_discovery_pipeline_public_api(monkeypatch, tmp_path: Path) -> None:
    cv_path = tmp_path / "cv.tex"
    cv_path.write_text("Python SQL FastAPI", encoding="utf-8")

    sample_match = _sample_match()
    collection_report = CollectionReport(
        sources=[SourceRunReport(key="remotive", label="Remotive", collected=1)],
        raw_total=1,
        filtered_age=0,
        filtered_score=0,
        filtered_stretch=0,
        filtered_salary=0,
        filtered_timezone=0,
        filtered_seniority=0,
        dedup_collisions=0,
        deduped_total=1,
    )
    llm_report = LLMRerankReport(
        adjusted=0,
        attempted=0,
        planned_calls=0,
        used_input_chars=0,
        dry_run=False,
        warnings=[],
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr("job_discovery_engine.pipeline.shared.extract_owned_skills_from_cv", lambda path: {"python", "sql"})
    monkeypatch.setattr("job_discovery_engine.pipeline.shared.infer_search_terms_for_profile", lambda owned, profile: ["backend engineer"])

    def fake_collect_matches(*, context: DiscoveryContext, **kwargs: object):
        captured["context"] = context
        return [sample_match], collection_report

    monkeypatch.setattr("job_discovery_engine.pipeline.collect_matches", fake_collect_matches)
    monkeypatch.setattr("job_discovery_engine.pipeline.rerankers.apply_llm_reranker", lambda matches, **kwargs: (matches, llm_report))
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.write_outputs",
        lambda strict_matches, broad_matches, report=None, output_dir=None: (
            tmp_path / "job_matches.csv",
            tmp_path / "job_matches_latest.md",
            tmp_path / "job_matches_broad.md",
        ),
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.write_application_notes",
        lambda matches, output_dir=None: tmp_path / "application_notes_latest.md",
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.sync_application_api",
        lambda matches, base_url, api_key, match_profile: (1, []),
    )
    monkeypatch.setattr("job_discovery_engine.pipeline.outputs.write_selected_jobs_checklist", lambda matches, output_dir=None: tmp_path / "selected_jobs.md")

    options = DiscoveryRunOptions(
        cv_path=cv_path,
        profile="de",
        api_base_url="http://127.0.0.1:8000",
        api_write_key="test-key",
        sources=["remotive"],
    )
    result, warnings = run_discovery_pipeline(options)

    assert result.context.profile == "de"
    assert captured["context"].profile == "de"
    assert result.strict_matches == [sample_match]
    assert result.synced_count == 1
    assert warnings.messages == []


# ---------------------------------------------------------------------------
# Session 10: read_cv_text, cv_word_bag, semantic scoring
# ---------------------------------------------------------------------------

def test_read_cv_text_plain_text(tmp_path: Path) -> None:
    txt = tmp_path / "resume.txt"
    txt.write_text("Python SQL FastAPI Airflow pipeline", encoding="utf-8")
    result = read_cv_text(txt)
    assert "Python" in result
    assert "Airflow" in result


def test_read_cv_text_strips_latex_for_tex_files(tmp_path: Path) -> None:
    tex = tmp_path / "cv.tex"
    tex.write_text(r"\textbf{Python} and \emph{Airflow} pipelines", encoding="utf-8")
    result = read_cv_text(tex)
    assert "Python" in result
    assert "Airflow" in result
    # LaTeX commands should be stripped
    assert "\\textbf" not in result
    assert "\\emph" not in result


def test_read_cv_text_pdf_raises_without_pypdf(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setitem(sys.modules, "pypdf", None)
    import pytest
    with pytest.raises(ImportError, match="pypdf is required"):
        read_cv_text(pdf)


def test_read_cv_text_pdf_with_mocked_pypdf(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "cv.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Python SQL Airflow"
    mock_reader_instance = MagicMock()
    mock_reader_instance.pages = [mock_page]
    mock_pypdf = MagicMock()
    mock_pypdf.PdfReader.return_value = mock_reader_instance
    monkeypatch.setitem(sys.modules, "pypdf", mock_pypdf)

    result = read_cv_text(pdf)
    assert "Python" in result
    assert "Airflow" in result


def test_cv_word_bag_extracts_content_words() -> None:
    text = "Python Airflow pipeline PostgreSQL FastAPI"
    bag = cv_word_bag(text)
    assert "python" in bag
    assert "airflow" in bag
    assert "pipeline" in bag
    assert "postgresql" in bag
    assert "fastapi" in bag


def test_cv_word_bag_excludes_stopwords() -> None:
    # "experience", "skills", "working" are in _CV_STOP_WORDS
    bag = cv_word_bag("experience skills working python airflow")
    assert "experience" not in bag
    assert "skills" not in bag
    assert "working" not in bag
    assert "python" in bag
    assert "airflow" in bag


def test_cv_word_bag_excludes_short_words() -> None:
    bag = cv_word_bag("data SQL api go rust")
    # None of these are >= 5 alpha chars
    assert "data" not in bag
    assert "sql" not in bag
    assert "api" not in bag


def test_score_match_semantic_boost_from_cv_words() -> None:
    cv_words_set = frozenset([
        "python", "airflow", "fastapi", "docker", "spark",
        "kafka", "postgres", "dbt", "pipeline", "orchestration",
        "monitoring", "deployment", "terraform", "gitlab",
    ])
    context_with_cv = DiscoveryContext(
        profile="de",
        owned_skills={"python"},
        search_terms=[],
        cv_words=cv_words_set,
    )
    context_without_cv = DiscoveryContext(
        profile="de",
        owned_skills={"python"},
        search_terms=[],
    )
    # Job text contains many domain words that overlap with cv_words
    job_details = (
        "Python Airflow FastAPI Docker Spark Kafka pipeline orchestration "
        "monitoring deployment Terraform GitLab senior engineer"
    )
    score_with = score_match("Data Engineer", job_details, context=context_with_cv)
    score_without = score_match("Data Engineer", job_details, context=context_without_cv)
    assert score_with > score_without


def test_discovery_context_cv_words_defaults_to_empty_frozenset() -> None:
    ctx = DiscoveryContext(profile="de", owned_skills={"python"}, search_terms=[])
    assert ctx.cv_words == frozenset()
    assert isinstance(ctx.cv_words, frozenset)


def test_run_discovery_pipeline_cv_words_in_context(monkeypatch, tmp_path: Path) -> None:
    cv_path = tmp_path / "cv.tex"
    # Include domain words that will be picked up by cv_word_bag
    cv_path.write_text("Python Airflow FastAPI Docker pipeline orchestration", encoding="utf-8")

    sample_match = _sample_match()
    collection_report = CollectionReport(
        sources=[SourceRunReport(key="remotive", label="Remotive", collected=1)],
        raw_total=1, filtered_age=0, filtered_score=0, filtered_stretch=0,
        filtered_salary=0, filtered_timezone=0, filtered_seniority=0,
        dedup_collisions=0, deduped_total=1,
    )
    llm_report = LLMRerankReport(
        adjusted=0, attempted=0, planned_calls=0, used_input_chars=0,
        dry_run=False, warnings=[],
    )
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        "job_discovery_engine.pipeline.shared.extract_owned_skills_from_cv",
        lambda path: {"python", "airflow"},
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.shared.infer_search_terms_for_profile",
        lambda owned, profile: ["data engineer"],
    )

    def fake_collect_matches(*, context: DiscoveryContext, **kwargs: object):
        captured["context"] = context
        return [sample_match], collection_report

    monkeypatch.setattr("job_discovery_engine.pipeline.collect_matches", fake_collect_matches)
    monkeypatch.setattr("job_discovery_engine.pipeline.rerankers.apply_llm_reranker", lambda matches, **kwargs: (matches, llm_report))
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.write_outputs",
        lambda strict_matches, broad_matches, report=None, output_dir=None: (
            tmp_path / "job_matches.csv",
            tmp_path / "job_matches_latest.md",
            tmp_path / "job_matches_broad.md",
        ),
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.write_application_notes",
        lambda matches, output_dir=None: tmp_path / "application_notes_latest.md",
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.sync_application_api",
        lambda matches, base_url, api_key, match_profile: (1, []),
    )
    monkeypatch.setattr(
        "job_discovery_engine.pipeline.outputs.write_selected_jobs_checklist",
        lambda matches, output_dir=None: tmp_path / "selected_jobs.md",
    )

    options = DiscoveryRunOptions(
        cv_path=cv_path,
        profile="de",
        api_base_url="http://127.0.0.1:8000",
        api_write_key="test-key",
        sources=["remotive"],
    )
    result, _warnings = run_discovery_pipeline(options)

    ctx = captured["context"]
    assert isinstance(ctx, DiscoveryContext)
    assert isinstance(ctx.cv_words, frozenset)
    # Domain words from cv.tex content should appear in cv_words
    assert "python" in ctx.cv_words
    assert "airflow" in ctx.cv_words
    assert "fastapi" in ctx.cv_words


# ---------------------------------------------------------------------------
# Session 11: user-level config (~/.config/job-discovery/config.json)
# ---------------------------------------------------------------------------

def test_user_config_path_constant_is_correct() -> None:
    assert USER_CONFIG_PATH == Path("~/.config/job-discovery/config.json").expanduser()
    assert isinstance(USER_CONFIG_PATH, Path)


def test_user_config_merged_before_project_override(tmp_path: Path, monkeypatch) -> None:
    user_cfg = {"scoring": {"extra_skills": ["trino"]}}
    project_cfg = {"scoring": {"extra_skills": ["flink"]}}

    user_path = tmp_path / "user_config.json"
    project_path = tmp_path / "project_config.json"
    user_path.write_text(json.dumps(user_cfg), encoding="utf-8")
    project_path.write_text(json.dumps(project_cfg), encoding="utf-8")

    monkeypatch.setattr("job_discovery_engine.config.USER_CONFIG_PATH", user_path)
    monkeypatch.setenv("DISCOVERY_CONFIG_PATH", str(project_path))

    merged = _load_discovery_config()

    # Project override wins over user config (both overwrite lists, not extend)
    assert isinstance(merged["scoring"]["extra_skills"], list)
    assert "flink" in merged["scoring"]["extra_skills"]


def test_user_config_applied_when_no_project_override(tmp_path: Path, monkeypatch) -> None:
    user_cfg = {"scoring": {"extra_skills": ["trino", "clickhouse"]}}
    user_path = tmp_path / "user_config.json"
    user_path.write_text(json.dumps(user_cfg), encoding="utf-8")

    # Point DISCOVERY_CONFIG_PATH at a non-existent file so no project override loads
    monkeypatch.setattr("job_discovery_engine.config.USER_CONFIG_PATH", user_path)
    monkeypatch.setenv("DISCOVERY_CONFIG_PATH", str(tmp_path / "nonexistent.json"))

    merged = _load_discovery_config()
    assert "trino" in merged["scoring"]["extra_skills"]
    assert "clickhouse" in merged["scoring"]["extra_skills"]


def test_user_config_malformed_json_falls_back_to_defaults(tmp_path: Path, monkeypatch) -> None:
    user_path = tmp_path / "bad_config.json"
    user_path.write_text("{ not valid json", encoding="utf-8")

    monkeypatch.setattr("job_discovery_engine.config.USER_CONFIG_PATH", user_path)
    monkeypatch.setenv("DISCOVERY_CONFIG_PATH", str(tmp_path / "nonexistent.json"))

    merged = _load_discovery_config()
    # Falls back to default: DEFAULT_DISCOVERY_CONFIG (no crash)
    assert "keyword_weights" in merged["scoring"]


def test_user_config_missing_is_skipped_silently(tmp_path: Path, monkeypatch) -> None:
    nonexistent = tmp_path / "no_user_config.json"
    monkeypatch.setattr("job_discovery_engine.config.USER_CONFIG_PATH", nonexistent)
    monkeypatch.setenv("DISCOVERY_CONFIG_PATH", str(tmp_path / "nonexistent.json"))

    merged = _load_discovery_config()
    assert "keyword_weights" in merged["scoring"]


def test_deep_merge_prefers_override_values() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
    override = {"a": {"y": 99, "z": 3}, "b": [9]}
    result = _deep_merge(base, override)
    assert result["a"]["x"] == 1
    assert result["a"]["y"] == 99
    assert result["a"]["z"] == 3
    assert result["b"] == [9]