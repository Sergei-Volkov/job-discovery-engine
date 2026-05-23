from __future__ import annotations

import argparse
from pathlib import Path

try:
    from . import shared
    from .pipeline import DiscoveryRunOptions, run_discovery_pipeline
    from .shared import DEFAULT_API_BASE_URL, DEFAULT_API_WRITE_KEY
except ImportError:  # pragma: no cover - script-mode fallback
    import shared
    from pipeline import DiscoveryRunOptions, run_discovery_pipeline
    from shared import DEFAULT_API_BASE_URL, DEFAULT_API_WRITE_KEY

APP_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = APP_ROOT.parent if (APP_ROOT.parent / "applications").exists() else APP_ROOT


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch remote data-engineering jobs aligned with the selected profile.")
    parser.add_argument("--cv-path", required=True, help="Path to CV file used to infer available skills.")
    parser.add_argument("--limit", type=int, default=40, help="Maximum number of rows to keep in the strict shortlist.")
    parser.add_argument("--min-score", type=int, default=7, help="Minimum fit score for the strict shortlist.")
    parser.add_argument(
        "--max-age-days", type=int, default=45, help="Maximum listing age to keep when a date is available."
    )
    parser.add_argument(
        "--include-stretch", action="store_true", help="Include low-fit stretch roles in the strict shortlist."
    )
    parser.add_argument(
        "--api-base-url",
        default=DEFAULT_API_BASE_URL,
        help="Base URL for the Job Application Insights API, e.g. http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory to write output files (md, csv). Defaults to applications/tracker.",
    )
    parser.add_argument(
        "--profile",
        default="de",
        choices=["de", "swe", "other"],
        help="Search profile: de (data engineering), swe (software engineering), other (broader adjacent).",
    )
    parser.add_argument(
        "--sources",
        default=",".join(shared.SOURCE_OPTIONS),
        help=(
            "Comma-separated source keys to query. "
            "Options: wwr, working_nomads, remoteok, remotive, arbeitnow, jobicy"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print source-by-source collection diagnostics and filtering summary.",
    )
    parser.add_argument(
        "--salary-min-usd",
        type=int,
        default=None,
        help="Optional minimum salary threshold in USD when salary data is present.",
    )
    parser.add_argument(
        "--timezones",
        default="",
        help="Comma-separated preferred timezone tokens, e.g. UTC,CET,EMEA,US.",
    )
    parser.add_argument(
        "--seniority",
        choices=["junior", "mid", "senior"],
        default=None,
        help="Minimum seniority level to include.",
    )
    parser.add_argument(
        "--use-outcome-priors",
        action="store_true",
        help="Re-rank matches based on historical source/role outcome performance.",
    )
    parser.add_argument(
        "--prior-lookback-days",
        type=int,
        default=365,
        help="How many days of historical applications to use when building priors.",
    )
    parser.add_argument(
        "--source-prior-weight",
        type=float,
        default=1.0,
        help="Weight multiplier for source-level outcome prior.",
    )
    parser.add_argument(
        "--role-prior-weight",
        type=float,
        default=1.0,
        help="Weight multiplier for role-family outcome prior.",
    )
    parser.add_argument(
        "--use-llm-reranker",
        action="store_true",
        help="Apply optional LLM-assisted reranking to top candidates.",
    )
    parser.add_argument(
        "--llm-top-n",
        type=int,
        default=20,
        help="How many top candidates to send to LLM reranker.",
    )
    parser.add_argument(
        "--llm-weight",
        type=float,
        default=1.0,
        help="Weight multiplier applied to LLM adjustment.",
    )
    parser.add_argument(
        "--llm-model",
        default="",
        help="Optional model name override for LLM reranker (defaults from env).",
    )
    parser.add_argument(
        "--llm-api-base-url",
        default="",
        help="Optional API base URL override for LLM reranker (defaults from env).",
    )
    parser.add_argument(
        "--llm-dry-run",
        action="store_true",
        help="Explain LLM reranker plan without sending external API requests.",
    )
    parser.add_argument(
        "--llm-max-calls",
        type=int,
        default=20,
        help="Hard cap on LLM calls per run.",
    )
    parser.add_argument(
        "--llm-max-input-chars",
        type=int,
        default=50000,
        help="Approximate per-run input char budget for LLM reranker.",
    )
    parser.add_argument(
        "--llm-max-retries",
        type=int,
        default=2,
        help="Max retries for transient LLM API failures.",
    )
    parser.add_argument(
        "--llm-retry-backoff-seconds",
        type=float,
        default=0.5,
        help="Base exponential backoff in seconds between LLM retries.",
    )
    parser.add_argument(
        "--llm-timeout-seconds",
        type=int,
        default=20,
        help="Timeout in seconds for each LLM API request.",
    )
    args = parser.parse_args()

    cv_path = Path(args.cv_path)
    if not cv_path.is_absolute():
        cv_path = (REPO_ROOT / cv_path).resolve()
    if not cv_path.exists():
        print(f"CV file not found: {cv_path}")
        return 2

    requested_sources = [part.strip().lower() for part in str(args.sources).split(",") if part.strip()]
    run_options = DiscoveryRunOptions(
        cv_path=cv_path,
        limit=args.limit,
        min_score=args.min_score,
        max_age_days=args.max_age_days,
        include_stretch=args.include_stretch,
        profile=args.profile,
        sources=requested_sources,
        salary_min_usd=args.salary_min_usd,
        timezones=[tz.strip() for tz in str(args.timezones).split(",") if tz.strip()],
        seniority=args.seniority,
        use_outcome_priors=args.use_outcome_priors,
        prior_lookback_days=args.prior_lookback_days,
        source_prior_weight=args.source_prior_weight,
        role_prior_weight=args.role_prior_weight,
        use_llm_reranker=args.use_llm_reranker,
        llm_top_n=args.llm_top_n,
        llm_weight=args.llm_weight,
        llm_model=args.llm_model or None,
        llm_api_base_url=args.llm_api_base_url or None,
        llm_dry_run=args.llm_dry_run,
        llm_max_calls=args.llm_max_calls,
        llm_max_input_chars=args.llm_max_input_chars,
        llm_max_retries=args.llm_max_retries,
        llm_retry_backoff_seconds=args.llm_retry_backoff_seconds,
        llm_timeout_seconds=args.llm_timeout_seconds,
        api_base_url=args.api_base_url,
        api_write_key=DEFAULT_API_WRITE_KEY,
        output_dir=Path(args.output_dir).resolve() if args.output_dir else None,
    )
    try:
        run_result, run_warnings = run_discovery_pipeline(run_options)
    except ValueError as exc:
        print(str(exc))
        return 2

    for warning in run_warnings.messages:
        print(f"Warning: {warning}")

    broad_matches = run_result.broad_matches
    strict_matches = run_result.strict_matches
    collection_report = run_result.collection_report
    llm_report = run_result.llm_report

    if not broad_matches:
        source_errors = [report for report in collection_report.sources if report.error]
        if source_errors:
            print("Source errors:")
            for report in source_errors:
                print(f"- {report.label} ({report.key}): {report.error}")
        print("No matches found this run.")
        return 1

    csv_path = run_result.csv_path
    md_path = run_result.strict_md_path
    broad_md_path = run_result.broad_md_path
    notes_path = run_result.notes_path
    checklist_path = run_result.checklist_path
    synced_count = run_result.synced_count
    failed_rows = run_result.failed_rows

    source_errors = [report for report in collection_report.sources if report.error]
    if args.verbose or source_errors:
        print("Source diagnostics:")
        for report in collection_report.sources:
            status = f"error={report.error}" if report.error else f"collected={report.collected}"
            print(f"- {report.label} ({report.key}): {status}")
    if args.verbose:
        print("Filter summary:")
        print(f"- raw_total={collection_report.raw_total}")
        print(f"- filtered_age={collection_report.filtered_age}")
        print(f"- filtered_score={collection_report.filtered_score}")
        print(f"- filtered_stretch={collection_report.filtered_stretch}")
        print(f"- filtered_salary={collection_report.filtered_salary}")
        print(f"- filtered_timezone={collection_report.filtered_timezone}")
        print(f"- filtered_seniority={collection_report.filtered_seniority}")
        print(f"- dedup_collisions={collection_report.dedup_collisions}")
        print(f"- deduped_total={collection_report.deduped_total}")
        if args.use_llm_reranker:
            print(f"- llm_dry_run={llm_report.dry_run}")
            print(f"- llm_planned_calls={llm_report.planned_calls}")
            print(f"- llm_attempted={llm_report.attempted}")
            print(f"- llm_adjusted={llm_report.adjusted}")
            print(f"- llm_used_input_chars={llm_report.used_input_chars}")
            if llm_report.warnings:
                print(f"- llm_warnings={len(llm_report.warnings)}")
                for warning in llm_report.warnings[:5]:
                    print(f"  {warning}")

    print(f"Saved {len(broad_matches)} total matches to: {csv_path}")
    print(f"Updated strict shortlist: {md_path}")
    print(f"Updated broad discovery list: {broad_md_path}")
    print(f"Updated notes: {notes_path}")
    print(f"Updated checklist: {checklist_path}")
    print(f"API upserts sent: {synced_count}")
    if failed_rows:
        print(f"API upserts failed: {len(failed_rows)}")
        status_counts: dict[str, int] = {}
        for row in failed_rows:
            status_label = str(row.status_code) if row.status_code is not None else row.error_type
            status_counts[status_label] = status_counts.get(status_label, 0) + 1

        if args.verbose:
            print("API upsert failures by status/error:")
            for status_label in sorted(status_counts):
                print(f"- {status_label}: {status_counts[status_label]}")

        if args.verbose:
            print("API upsert failure samples:")
            for row in failed_rows[:5]:
                status_label = str(row.status_code) if row.status_code is not None else row.error_type
                print(f"- {row.company} | {row.title} | {row.source} | {status_label} | {row.message}")

        unauthorized_count = status_counts.get("401", 0)
        if unauthorized_count:
            print(
                "Warning: Received 401 Unauthorized during API upserts. Check JOB_SEARCH_WRITE_API_KEY and backend key settings."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
