
from dataclasses import dataclass
from pathlib import Path

try:
    from . import outputs, rerankers, shared
    from .models import ApiUpsertFailure, CollectionReport, DiscoveryContext, JobMatch
    from .rerankers import LLMRerankReport
    from .shared import OutcomePriors
    from .sources import collect_matches
except ImportError:  # pragma: no cover - script-mode fallback
    import outputs
    import rerankers
    import shared
    from models import ApiUpsertFailure, CollectionReport, DiscoveryContext, JobMatch
    from rerankers import LLMRerankReport
    from shared import OutcomePriors
    from sources import collect_matches


@dataclass
class DiscoveryRunOptions:
    cv_path: Path
    limit: int = 40
    min_score: int = 7
    max_age_days: int = 45
    include_stretch: bool = False
    profile: str = "de"
    sources: list[str] | None = None
    salary_min_usd: int | None = None
    timezones: list[str] | None = None
    seniority: str | None = None
    use_outcome_priors: bool = False
    prior_lookback_days: int = 365
    source_prior_weight: float = 1.0
    role_prior_weight: float = 1.0
    use_llm_reranker: bool = False
    llm_top_n: int = 20
    llm_weight: float = 1.0
    llm_model: str | None = None
    llm_api_base_url: str | None = None
    llm_dry_run: bool = False
    llm_max_calls: int = 20
    llm_max_input_chars: int = 50_000
    llm_max_retries: int = 2
    llm_retry_backoff_seconds: float = 0.5
    llm_timeout_seconds: int = 20
    api_base_url: str = shared.DEFAULT_API_BASE_URL
    api_write_key: str = shared.DEFAULT_API_WRITE_KEY
    output_dir: Path | None = None


@dataclass
class DiscoveryRunResult:
    context: DiscoveryContext
    strict_matches: list[JobMatch]
    broad_matches: list[JobMatch]
    collection_report: CollectionReport
    llm_report: LLMRerankReport
    csv_path: Path
    strict_md_path: Path
    broad_md_path: Path
    notes_path: Path
    checklist_path: Path
    synced_count: int
    failed_rows: list[ApiUpsertFailure]


@dataclass
class DiscoveryRunWarnings:
    messages: list[str]


def run_discovery_pipeline(options: DiscoveryRunOptions) -> tuple[DiscoveryRunResult, DiscoveryRunWarnings]:
    warnings: list[str] = []

    cv_path = options.cv_path
    owned_skills = shared.extract_owned_skills_from_cv(cv_path)
    if not owned_skills:
        raise ValueError(f"No recognizable skills found in CV: {cv_path}")

    context = DiscoveryContext(
        profile=options.profile,
        owned_skills=owned_skills,
        search_terms=shared.infer_search_terms_for_profile(owned_skills, options.profile),
    )

    effective_output_dir = options.output_dir.resolve() if options.output_dir else None

    if not options.api_write_key:
        warnings.append("JOB_SEARCH_WRITE_API_KEY is not set; API upserts will likely fail with 401 Unauthorized.")
    elif len(options.api_write_key.strip()) < 8:
        warnings.append("JOB_SEARCH_WRITE_API_KEY looks unusually short; verify the value if API upserts fail.")

    requested_sources = [part.strip().lower() for part in (options.sources or []) if part.strip()]
    requested_sources = [source for source in requested_sources if source in shared.SOURCE_OPTIONS]
    if not requested_sources:
        requested_sources = shared.SOURCE_OPTIONS.copy()

    priors = OutcomePriors(source={}, role_family={})
    if options.use_outcome_priors:
        try:
            headers: dict[str, str] = {}
            if options.api_write_key:
                headers["X-API-Key"] = options.api_write_key
            payload = shared.fetch_json(
                options.api_base_url.rstrip("/") + "/applications?limit=1000",
                extra_headers=headers,
            )
            if isinstance(payload, list):
                rows = [row for row in payload if isinstance(row, dict)]
                priors = shared.build_outcome_priors(rows, lookback_days=options.prior_lookback_days)
        except Exception as exc:
            warnings.append(f"unable to load outcome priors: {exc}")

    broad_matches, collection_report = collect_matches(
        limit=max(options.limit * 3, 120),
        min_score=1,
        max_age_days=options.max_age_days,
        include_stretch=True,
        salary_min_usd=options.salary_min_usd,
        allowed_timezones=options.timezones or None,
        seniority=options.seniority,
        sources=requested_sources,
        context=context,
    )
    if options.use_outcome_priors and (priors.source or priors.role_family):
        broad_matches = shared.apply_outcome_priors(
            broad_matches,
            priors,
            source_weight=options.source_prior_weight,
            role_weight=options.role_prior_weight,
        )
        broad_matches = sorted(
            broad_matches,
            key=lambda row: (-row.score, row.freshness, row.title.lower()),
        )

    broad_matches, llm_report = rerankers.apply_llm_reranker(
        broad_matches,
        profile=context.profile,
        enabled=options.use_llm_reranker,
        top_n=options.llm_top_n,
        weight=options.llm_weight,
        model=options.llm_model,
        api_base_url=options.llm_api_base_url,
        dry_run=options.llm_dry_run,
        max_calls=options.llm_max_calls,
        max_input_chars=options.llm_max_input_chars,
        max_retries=options.llm_max_retries,
        retry_backoff_seconds=options.llm_retry_backoff_seconds,
        timeout_seconds=options.llm_timeout_seconds,
    )

    strict_matches = [
        item
        for item in broad_matches
        if item.score >= options.min_score and (options.include_stretch or item.fit != "Stretch")
    ][: options.limit]

    csv_path, strict_md_path, broad_md_path = outputs.write_outputs(
        strict_matches, broad_matches, collection_report, output_dir=effective_output_dir
    )
    notes_path = outputs.write_application_notes(strict_matches, output_dir=effective_output_dir)
    synced_count, failed_rows = outputs.sync_application_api(
        strict_matches,
        options.api_base_url,
        options.api_write_key,
        match_profile=context.profile,
    )
    checklist_path = outputs.write_selected_jobs_checklist(strict_matches, output_dir=effective_output_dir)

    result = DiscoveryRunResult(
        context=context,
        strict_matches=strict_matches,
        broad_matches=broad_matches,
        collection_report=collection_report,
        llm_report=llm_report,
        csv_path=csv_path,
        strict_md_path=strict_md_path,
        broad_md_path=broad_md_path,
        notes_path=notes_path,
        checklist_path=checklist_path,
        synced_count=synced_count,
        failed_rows=failed_rows,
    )
    return result, DiscoveryRunWarnings(messages=warnings)
