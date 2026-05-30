
import re
from datetime import datetime
from pathlib import Path

try:
    from . import config
    from .models import DiscoveryContext, JobMatch, OutcomePriors
    from .text_utils import days_old, normalize, strip_latex
except ImportError:  # pragma: no cover - script-mode fallback
    import config
    from models import DiscoveryContext, JobMatch, OutcomePriors
    from text_utils import days_old, normalize, strip_latex


def _runtime_context(context: DiscoveryContext | None) -> DiscoveryContext:
    if context is not None:
        return context
    return DiscoveryContext(
        profile=config.ACTIVE_PROFILE,
        owned_skills=set(config.OWNED_SKILLS),
        search_terms=list(config.SEARCH_TERMS),
    )


def extract_owned_skills_from_cv(cv_path: Path) -> set[str]:
    raw_text = cv_path.read_text(encoding="utf-8", errors="ignore")
    text = strip_latex(raw_text).lower()
    owned: set[str] = set()

    for skill, patterns in config.SKILL_PATTERNS.items():
        if any(re.search(pattern, text) for pattern in patterns):
            owned.add(skill)

    if "postgres" in owned:
        owned.add("postgresql")
    if "pipeline" in owned:
        owned.add("etl")

    # Extra skills from discovery_config override: matched as plain substrings.
    for skill in config.EXTRA_SKILLS:
        if skill.strip().lower() in text:
            owned.add(skill.strip().lower())

    return owned


def infer_search_terms_for_profile(owned_skills: set[str], profile: str) -> list[str]:
    terms = config.PROFILE_SEARCH_TERMS.get(profile, config.PROFILE_SEARCH_TERMS["de"]).copy()
    if profile in {"de", "other"}:
        if "airflow" in owned_skills and "airflow" not in terms:
            terms.append("airflow")
        if ("etl" in owned_skills or "elt" in owned_skills) and "etl" not in terms:
            terms.append("etl")
    if profile == "sre":
        if "kubernetes" in owned_skills and "kubernetes" not in terms:
            terms.append("kubernetes")
        if "terraform" in owned_skills and "terraform" not in terms:
            terms.append("terraform")
        if "ansible" in owned_skills and "ansible" not in terms:
            terms.append("ansible")
    return terms


def profile_title_signals(profile: str) -> list[str]:
    if profile == "swe":
        return ["software engineer", "backend engineer", "platform engineer", "infrastructure", "devops"]
    if profile == "sre":
        return [
            "site reliability",
            "sre",
            "platform engineer",
            "devops engineer",
            "infrastructure engineer",
            "cloud engineer",
            "reliability engineer",
        ]
    if profile == "other":
        return [
            "data engineer",
            "analytics engineer",
            "software engineer",
            "backend engineer",
            "platform engineer",
            "devops",
        ]
    return [
        "data engineer",
        "analytics engineer",
        "data platform",
        "data ops",
        "data devops",
        "etl developer",
        "bi engineer",
    ]


def profile_reject_patterns(profile: str) -> list[str]:
    if profile == "swe":
        return ["data scientist", "data annotator", "marketing analytics", "manager", "director", "volunteer"]
    if profile == "sre":
        return [
            "data scientist",
            "data annotator",
            "marketing analytics",
            "manager",
            "director",
            "volunteer",
            "talent community",
            "frontend",
            "front end",
        ]
    if profile == "other":
        return ["manager", "director", "volunteer", "talent community"]
    return config.REJECT_PATTERNS


def is_relevant(title: str, details: str, context: DiscoveryContext | None = None) -> bool:
    runtime = _runtime_context(context)
    title_lower = title.lower()
    details_lower = details.lower()
    if any(bad in title_lower for bad in profile_reject_patterns(runtime.profile)):
        return False

    strong_title_signals = profile_title_signals(runtime.profile)
    if any(signal in title_lower for signal in strong_title_signals):
        return True

    has_data_word = re.search(r"\bdata\b", title_lower) is not None
    has_role_word = (
        re.search(r"\b(engineer|platform|warehouse|analytics|etl|elt|devops|backend|software)\b", title_lower)
        is not None
    )
    if has_data_word and has_role_word:
        return True

    adjacent_title = re.search(r"\b(devops|platform|backend|software|infrastructure)\b", title_lower) is not None
    stack_hits = sum(
        keyword in details_lower
        for keyword in [
            "airflow",
            "dbt",
            "databricks",
            "bigquery",
            "snowflake",
            "etl",
            "warehouse",
            "pipeline",
            "analytics",
        ]
    )
    return bool(adjacent_title and stack_hits >= 2)


def score_match(title: str, details: str, context: DiscoveryContext | None = None) -> int:
    runtime = _runtime_context(context)
    text = f"{title} {details}".lower()
    title_lower = title.lower()
    score = 0
    for keyword, weight in config.KEYWORD_WEIGHTS.items():
        if keyword in text:
            score += weight if keyword in runtime.owned_skills else 1
    if "data engineer" in title_lower:
        score += 6
    if runtime.profile == "swe" and ("software engineer" in title_lower or "backend engineer" in title_lower):
        score += 5
    if runtime.profile == "sre" and (
        "site reliability" in title_lower
        or "sre" in title_lower
        or "reliability engineer" in title_lower
    ):
        score += 6
    if runtime.profile == "sre" and (
        "platform engineer" in title_lower
        or "devops engineer" in title_lower
        or "infrastructure engineer" in title_lower
        or "cloud engineer" in title_lower
    ):
        score += 4
    if runtime.profile == "other" and ("software engineer" in title_lower or "backend engineer" in title_lower):
        score += 3
    if "analytics engineer" in title_lower:
        score += 5
    if "data platform" in title_lower or "data ops" in title_lower or "data devops" in title_lower:
        score += 4
    if "remote" in text or "world" in text or "emea" in text or "europe" in text:
        score += 1
    return score


def fit_label(score: int) -> str:
    if score >= config.SCORE_STRONG_MIN:
        return "Strong"
    if score >= config.SCORE_MEDIUM_MIN:
        return "Medium"
    return "Stretch"


def infer_seniority(title: str, details: str) -> str:
    text = f"{title} {details}".lower()
    if any(token in text for token in ["staff", "principal"]):
        return "staff"
    if "lead" in text:
        return "lead"
    if any(token in text for token in ["senior", "sr.", "sr "]):
        return "senior"
    if any(token in text for token in ["junior", "jr.", "jr ", "entry level", "intern"]):
        return "junior"
    return "mid"


def matches_seniority(title: str, details: str, requested: str | None) -> bool:
    if not requested:
        return True
    req = requested.strip().lower()
    if req not in {"junior", "mid", "senior"}:
        return True
    detected = infer_seniority(title, details)
    return config.SENIORITY_LEVELS[detected] >= config.SENIORITY_LEVELS[req]


def extract_salary_ceiling_usd(text: str) -> int | None:
    lower = text.lower()
    if not any(token in lower for token in ["$", "usd", "salary", "compensation", "pay", "rate"]):
        return None

    amounts: list[int] = []
    for match in re.finditer(r"(\d{2,3})(\s?)(k)\b", lower):
        amounts.append(int(match.group(1)) * 1000)

    for match in re.finditer(r"\b(\d{4,6})\b", lower):
        value = int(match.group(1))
        if 10_000 <= value <= 1_000_000:
            amounts.append(value)

    if not amounts:
        return None
    return max(amounts)


def matches_salary_requirement(title: str, details: str, minimum_usd: int | None) -> bool:
    if minimum_usd is None or minimum_usd <= 0:
        return True
    ceiling = extract_salary_ceiling_usd(f"{title} {details}")
    if ceiling is None:
        return True
    return ceiling >= minimum_usd


def matches_timezone(remote_policy: str, details: str, allowed_timezones: list[str] | None) -> bool:
    if not allowed_timezones:
        return True
    text = f"{remote_policy} {details}".lower()
    normalized_allowed = [tz.strip().lower() for tz in allowed_timezones if tz and tz.strip()]
    if not normalized_allowed:
        return True
    if any(token in text for token in normalized_allowed):
        return True
    return "remote" in text and "only" not in text


def extract_keywords(text: str, context: DiscoveryContext | None = None) -> tuple[list[str], list[str]]:
    runtime = _runtime_context(context)
    lower = text.lower()
    owned: list[str] = []
    missing: list[str] = []
    for keyword in config.KEYWORD_WEIGHTS:
        if keyword in lower:
            label = config.DISPLAY_NAMES[keyword]
            if keyword in runtime.owned_skills:
                if label not in owned:
                    owned.append(label)
            else:
                if label not in missing:
                    missing.append(label)
    return owned, missing


def build_fit_note(
    title: str,
    details: str,
    remote_policy: str,
    context: DiscoveryContext | None = None,
) -> tuple[str, str, str]:
    matched_keywords, missing_keywords = extract_keywords(f"{title} {details}", context=context)
    parts: list[str] = []
    if matched_keywords:
        parts.append(f"Direct overlap on {', '.join(matched_keywords[:6])}")
    if missing_keywords:
        parts.append(f"missing or adjacent tools: {', '.join(missing_keywords[:5])}")
    if remote_policy in {"Worldwide", "EMEA", "Europe", "Remote"}:
        parts.append("remote setup looks workable")
    note = ". ".join(parts).strip()
    if note and not note.endswith("."):
        note += "."
    return (
        ", ".join(matched_keywords),
        ", ".join(missing_keywords),
        note or "General overlap with your data-engineering profile.",
    )


def next_step_for_fit(fit: str) -> str:
    if fit == "Strong":
        return "Tailor CV and apply soon"
    if fit == "Medium":
        return "Review requirements and tailor selectively"
    return "Keep as backup option"


def tailoring_points(match: JobMatch) -> list[str]:
    keywords = {item.strip() for item in match.matched_keywords.split(",") if item.strip()}
    points = ["Highlight Python and SQL pipeline development experience."]

    if "Airflow" in keywords:
        points.append("Emphasize Airflow orchestration and batch workflow reliability.")
    if "data quality" in keywords:
        points.append("Use the 20% data-quality improvement result prominently.")
    if "analytics" in keywords or "reporting" in keywords:
        points.append("Stress analytics-ready datasets and reporting support.")
    if "AWS" in keywords or "Docker" in keywords:
        points.append("Mention cloud and containerized delivery experience.")
    if any(item in keywords for item in ["dbt", "BigQuery", "GCP", "Databricks", "Terraform", "Snowflake"]):
        points.append("Call out quick ramp-up on adjacent platform tooling.")

    deduped: list[str] = []
    for point in points:
        if point not in deduped:
            deduped.append(point)
    return deduped[:4]


def build_job_match(
    title: str,
    company: str,
    source: str,
    remote_policy: str,
    freshness: str,
    url: str,
    details: str,
    context: DiscoveryContext | None = None,
) -> JobMatch:
    score = score_match(title, details, context=context)
    matched_keywords, missing_skills, fit_notes = build_fit_note(title, details, remote_policy, context=context)
    return JobMatch(
        title=title,
        company=company or "Unknown",
        source=source,
        remote_policy=remote_policy or "Not stated",
        freshness=freshness or "n/a",
        fit=fit_label(score),
        score=score,
        url=url,
        details_text=normalize(details),
        matched_keywords=matched_keywords,
        missing_skills=missing_skills,
        fit_notes=fit_notes,
    )


def classify_role_family(title: str) -> str:
    lower = title.lower()
    if any(token in lower for token in ["data engineer", "etl", "pipeline", "warehouse"]):
        return "data_engineering"
    if "analytics engineer" in lower:
        return "analytics_engineering"
    if any(token in lower for token in ["backend", "software engineer", "api", "services"]):
        return "backend"
    if any(token in lower for token in ["platform", "infrastructure", "devops", "sre"]):
        return "platform"
    return "other"


def status_outcome_weight(status: str) -> float:
    lower = status.strip().lower()
    if "offer" in lower:
        return 3.0
    if "interview" in lower:
        return 2.0
    if "applied" in lower:
        return 1.0
    if "rejected" in lower:
        return -2.0
    return 0.0


def build_outcome_priors(
    rows: list[dict[str, object]],
    lookback_days: int = 365,
    min_samples: int = 3,
) -> OutcomePriors:
    source_scores: dict[str, list[float]] = {}
    role_scores: dict[str, list[float]] = {}

    for row in rows:
        date_found = normalize(row.get("date_found"))
        age = days_old(date_found)
        if age is not None and age > max(lookback_days, 1):
            continue

        status = normalize(row.get("status"))
        weight = status_outcome_weight(status)
        if weight == 0:
            continue

        source_key = normalize(row.get("source")).lower()
        role = normalize(row.get("role"))
        role_family = classify_role_family(role)

        if source_key:
            source_scores.setdefault(source_key, []).append(weight)
        role_scores.setdefault(role_family, []).append(weight)

    def summarize(scores: dict[str, list[float]]) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, values in scores.items():
            if len(values) < min_samples:
                continue
            avg = sum(values) / len(values)
            out[key] = max(-2.0, min(2.0, avg))
        return out

    return OutcomePriors(
        source=summarize(source_scores),
        role_family=summarize(role_scores),
    )


def apply_outcome_priors(
    matches: list[JobMatch],
    priors: OutcomePriors,
    source_weight: float,
    role_weight: float,
) -> list[JobMatch]:
    adjusted: list[JobMatch] = []
    for item in matches:
        source_key = item.source.strip().lower()
        role_family = classify_role_family(item.title)
        source_bonus = priors.source.get(source_key, 0.0)
        role_bonus = priors.role_family.get(role_family, 0.0)
        delta = source_bonus * source_weight + role_bonus * role_weight
        if delta == 0:
            adjusted.append(item)
            continue
        bumped = int(round(delta))
        new_score = max(0, item.score + bumped)
        adjusted.append(
            JobMatch(
                title=item.title,
                company=item.company,
                source=item.source,
                remote_policy=item.remote_policy,
                freshness=item.freshness,
                fit=fit_label(new_score),
                score=new_score,
                url=item.url,
                details_text=item.details_text,
                matched_keywords=item.matched_keywords,
                missing_skills=item.missing_skills,
                fit_notes=item.fit_notes,
            )
        )
    return adjusted
