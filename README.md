# job-discovery-engine

Discovery package extracted from the job application insights app.

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