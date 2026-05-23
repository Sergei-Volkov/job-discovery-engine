
import json
import os
from pathlib import Path


# Canonical package defaults. These values are intentionally versioned in-repo
# so CLI/API behavior stays deterministic unless an explicit override is provided.
DEFAULT_DISCOVERY_CONFIG = {
    "sources": {
        "wwr_feeds": [
            "https://weworkremotely.com/categories/all-other-remote-jobs.rss",
            "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
            "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
            "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
        ],
        "jobicy_feed": "https://jobicy.com/?feed=job_feed",
        "working_nomads_api": "https://www.workingnomads.com/api/exposed_jobs/",
        "remoteok_api": "https://remoteok.com/api",
        "remotive_api": "https://remotive.com/api/remote-jobs?search={query}",
        "arbeitnow_api": "https://www.arbeitnow.com/api/job-board-api",
        "source_options": ["wwr", "working_nomads", "remoteok", "remotive", "arbeitnow", "jobicy"],
    },
    "profiles": {
        "search_terms": {
            "de": ["data engineer", "analytics engineer", "data platform", "airflow", "etl"],
            "swe": ["software engineer", "backend engineer", "platform engineer", "infrastructure engineer"],
            "other": ["data engineer", "software engineer", "platform engineer", "etl", "backend engineer"],
        },
        "default_search_terms": ["data engineer", "analytics engineer", "data platform", "airflow", "etl"],
        "reject_patterns": [
            "data scientist",
            "data annotator",
            "marketing analytics",
            "ga4",
            "gtm",
            "manager",
            "director",
            "frontend",
            "front end",
            "full stack",
            "prompt engineering",
            "dataannotation",
            "voip",
            "volunteer",
            "talent community",
        ],
    },
    "scoring": {
        "keyword_weights": {
            "python": 3,
            "sql": 3,
            "airflow": 3,
            "etl": 2,
            "elt": 2,
            "postgres": 2,
            "postgresql": 2,
            "docker": 2,
            "aws": 2,
            "dbt": 2,
            "databricks": 2,
            "bigquery": 2,
            "gcp": 2,
            "terraform": 1,
            "analytics": 1,
            "reporting": 1,
            "data quality": 2,
            "pipeline": 2,
            "warehouse": 1,
            "snowflake": 2,
        },
        "display_names": {
            "python": "Python",
            "sql": "SQL",
            "airflow": "Airflow",
            "etl": "ETL",
            "elt": "ELT",
            "postgres": "PostgreSQL",
            "postgresql": "PostgreSQL",
            "docker": "Docker",
            "aws": "AWS",
            "dbt": "dbt",
            "databricks": "Databricks",
            "bigquery": "BigQuery",
            "gcp": "GCP",
            "terraform": "Terraform",
            "analytics": "analytics",
            "reporting": "reporting",
            "data quality": "data quality",
            "pipeline": "pipelines",
            "warehouse": "data warehousing",
            "snowflake": "Snowflake",
        },
        "skill_patterns": {
            "python": ["\\bpython\\b"],
            "sql": ["\\bsql\\b", "sqlalchemy"],
            "airflow": ["\\bairflow\\b"],
            "etl": ["\\betl\\b", "pipelines?"],
            "elt": ["\\belt\\b"],
            "postgres": ["\\bpostgres\\b", "\\bpostgresql\\b"],
            "postgresql": ["\\bpostgresql\\b"],
            "docker": ["\\bdocker\\b"],
            "aws": ["\\baws\\b"],
            "analytics": ["\\banalytics\\b", "analysis-ready", "reporting"],
            "reporting": ["\\breporting\\b"],
            "data quality": ["data quality", "validation"],
            "pipeline": ["pipelines?"],
            "warehouse": ["warehouse", "warehouse-ready"],
        },
        "seniority_levels": {
            "junior": 1,
            "mid": 2,
            "senior": 3,
            "lead": 4,
            "staff": 5,
        },
        "score_strong_min": 12,
        "score_medium_min": 7,
    },
}


def _deep_merge(base: dict[str, object], override: dict[str, object]) -> dict[str, object]:
    merged: dict[str, object] = dict(base)
    for key, value in override.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(base_value, value)
        else:
            merged[key] = value
    return merged


def _as_string_list(value: object, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    out = [str(item).strip() for item in value if str(item).strip()]
    return out or fallback


def _as_string_map(value: object, fallback: dict[str, str]) -> dict[str, str]:
    if not isinstance(value, dict):
        return fallback
    out: dict[str, str] = {}
    for key, item in value.items():
        raw_key = str(key).strip()
        raw_value = str(item).strip()
        if raw_key and raw_value:
            out[raw_key] = raw_value
    return out or fallback


def _as_int_map(value: object, fallback: dict[str, int]) -> dict[str, int]:
    if not isinstance(value, dict):
        return fallback
    out: dict[str, int] = {}
    for key, item in value.items():
        raw_key = str(key).strip()
        if not raw_key:
            continue
        try:
            out[raw_key] = int(item)
        except (TypeError, ValueError):
            continue
    return out or fallback


def _as_profile_terms(value: object, fallback: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return fallback
    out: dict[str, list[str]] = {}
    for key, item in value.items():
        raw_key = str(key).strip().lower()
        if not raw_key:
            continue
        out[raw_key] = _as_string_list(item, fallback.get(raw_key, []))
    return out or fallback


def _load_discovery_config() -> dict[str, object]:
    # Default to package-local JSON so discovery works without any env setup.
    default_path = Path(__file__).resolve().parent / "discovery_config.json"
    config_path = Path(os.environ.get("DISCOVERY_CONFIG_PATH", str(default_path))).expanduser()

    # Resolve relative override paths from the caller's working directory.
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()

    if not config_path.exists():
        return DEFAULT_DISCOVERY_CONFIG

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_DISCOVERY_CONFIG

    if not isinstance(payload, dict):
        return DEFAULT_DISCOVERY_CONFIG

    return _deep_merge(DEFAULT_DISCOVERY_CONFIG, payload)


_loaded_config = _load_discovery_config()

_sources_cfg = _loaded_config.get("sources", {}) if isinstance(_loaded_config, dict) else {}
_profiles_cfg = _loaded_config.get("profiles", {}) if isinstance(_loaded_config, dict) else {}
_scoring_cfg = _loaded_config.get("scoring", {}) if isinstance(_loaded_config, dict) else {}

WWR_FEEDS = _as_string_list(_sources_cfg.get("wwr_feeds"), DEFAULT_DISCOVERY_CONFIG["sources"]["wwr_feeds"])
JOBICY_FEED = str(_sources_cfg.get("jobicy_feed") or DEFAULT_DISCOVERY_CONFIG["sources"]["jobicy_feed"])
WORKING_NOMADS_API = str(
    _sources_cfg.get("working_nomads_api") or DEFAULT_DISCOVERY_CONFIG["sources"]["working_nomads_api"]
)
REMOTEOK_API = str(_sources_cfg.get("remoteok_api") or DEFAULT_DISCOVERY_CONFIG["sources"]["remoteok_api"])
REMOTIVE_API = str(_sources_cfg.get("remotive_api") or DEFAULT_DISCOVERY_CONFIG["sources"]["remotive_api"])
ARBEITNOW_API = str(_sources_cfg.get("arbeitnow_api") or DEFAULT_DISCOVERY_CONFIG["sources"]["arbeitnow_api"])

SEARCH_TERMS = _as_string_list(
    _profiles_cfg.get("default_search_terms"),
    DEFAULT_DISCOVERY_CONFIG["profiles"]["default_search_terms"],
)
PROFILE_SEARCH_TERMS = _as_profile_terms(
    _profiles_cfg.get("search_terms"),
    DEFAULT_DISCOVERY_CONFIG["profiles"]["search_terms"],
)

SOURCE_OPTIONS = _as_string_list(
    _sources_cfg.get("source_options"),
    DEFAULT_DISCOVERY_CONFIG["sources"]["source_options"],
)

KEYWORD_WEIGHTS = _as_int_map(
    _scoring_cfg.get("keyword_weights"),
    DEFAULT_DISCOVERY_CONFIG["scoring"]["keyword_weights"],
)

DISPLAY_NAMES = _as_string_map(
    _scoring_cfg.get("display_names"),
    DEFAULT_DISCOVERY_CONFIG["scoring"]["display_names"],
)

SKILL_PATTERNS = {
    key: _as_string_list(value, [])
    for key, value in (_scoring_cfg.get("skill_patterns") or DEFAULT_DISCOVERY_CONFIG["scoring"]["skill_patterns"]).items()
}

REJECT_PATTERNS = _as_string_list(
    _profiles_cfg.get("reject_patterns"),
    DEFAULT_DISCOVERY_CONFIG["profiles"]["reject_patterns"],
)

SENIORITY_LEVELS = _as_int_map(
    _scoring_cfg.get("seniority_levels"),
    DEFAULT_DISCOVERY_CONFIG["scoring"]["seniority_levels"],
)

try:
    SCORE_STRONG_MIN = int(_scoring_cfg.get("score_strong_min", DEFAULT_DISCOVERY_CONFIG["scoring"]["score_strong_min"]))
except (TypeError, ValueError):
    SCORE_STRONG_MIN = int(DEFAULT_DISCOVERY_CONFIG["scoring"]["score_strong_min"])

try:
    SCORE_MEDIUM_MIN = int(_scoring_cfg.get("score_medium_min", DEFAULT_DISCOVERY_CONFIG["scoring"]["score_medium_min"]))
except (TypeError, ValueError):
    SCORE_MEDIUM_MIN = int(DEFAULT_DISCOVERY_CONFIG["scoring"]["score_medium_min"])

DEFAULT_API_BASE_URL = os.environ.get("JOB_SEARCH_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_API_WRITE_KEY = os.environ.get("JOB_SEARCH_WRITE_API_KEY", "")

# Mutable runtime globals tuned by cli.py
OWNED_SKILLS = set(SKILL_PATTERNS)
ACTIVE_PROFILE = "de"
