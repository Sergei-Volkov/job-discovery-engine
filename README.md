# job-discovery-engine

Discovery package extracted from the job application insights app.

## Install

Pinned release install:

```bash
pip install "job-discovery-engine @ git+https://github.com/Sergei-Volkov/job-discovery-engine.git@v0.1.0"
```

Editable local dev install:

```bash
pip install -e .
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

## App Integration Notes
- The app backend can run discovery in `module` mode (direct import) or `subprocess` mode (CLI wrapper).
- The app may use `DISCOVERY_CONFIG_PATH` to point to a local override JSON file.
- Keep releases semver-compatible with `API_CONTRACT.md`.