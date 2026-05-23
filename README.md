# job-discovery-engine

Discovery package extracted from the job application insights app.

## What this package does
- Collects remote job listings from multiple sources.
- Scores and filters listings against CV-derived skills and profile settings.
- Optionally reranks top matches with an LLM.
- Writes tracker artifacts and can sync shortlisted roles back to an API.

## Install

Pinned release install:

```bash
pip install "job-discovery-engine @ git+https://github.com/Sergei-Volkov/job-discovery-engine.git@v0.1.0"
```

Editable local dev install:

```bash
pip install -e .
```

## Quickstart (5 minutes)
1. Clone repo and enter it.
2. Install package: `pip install -e .`
3. Run help: `python -m job_discovery_engine.cli --help`
4. Run a dry pass:

```bash
python -m job_discovery_engine.cli \
	--cv-path ../applications/resumes/CV.tex \
	--profile de \
	--limit 30 \
	--min-score 7 \
	--llm-dry-run
```

## Public contract
- `DiscoveryContext`
- `DiscoveryRunOptions`
- `DiscoveryRunResult`
- `DiscoveryRunWarnings`
- `run_discovery_pipeline(options)`

## Contents
- `src/job_discovery_engine/`: runtime package
- `API_CONTRACT.md`: frozen public surface
- `EXTRACTION_PLAN.md`: migration checklist

## Local run
```bash
python -m job_discovery_engine.cli --help
```

## Workflow and outputs
- Main outputs are written under `applications/tracker` by default:
	- `job_matches_latest.md`
	- `job_matches_broad.md`
	- `job_matches_<timestamp>.csv`
	- `application_notes_latest.md`
	- `selected_jobs.md`
- Use `--output-dir` to write artifacts elsewhere.

## Configuration and caveats
- Defaults are loaded from `src/job_discovery_engine/discovery_config.json`.
- To override selectively, set `DISCOVERY_CONFIG_PATH` to a JSON file; values are deep-merged over defaults.
- If API sync is enabled, ensure API base URL and write key are valid.
- LLM reranker requires provider credentials unless `--llm-dry-run` is used.

## Integration note for job-application-insights
- App backend imports this package directly and calls `run_discovery_pipeline`.
- Keep releases semver-compatible with `API_CONTRACT.md`.