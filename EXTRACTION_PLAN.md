# Discovery Extraction Plan

Extraction status: completed.

This file is now a short maintenance checklist for post-extraction evolution.

## Current state
- Public API is in `src/job_discovery_engine/api.py`.
- Orchestration is in `src/job_discovery_engine/pipeline.py`.
- Runtime state is explicit via `DiscoveryContext`.
- `job-application-insights` consumes this repo as a pinned dependency.

## Ongoing contract
- Keep app-facing imports limited to: `DiscoveryContext`, `DiscoveryRunOptions`, `DiscoveryRunResult`, `DiscoveryRunWarnings`, `run_discovery_pipeline`.
- Patch releases: behavior fixes only.
- Minor releases: additive fields/options with safe defaults.
- Major releases: allowed breaking changes with migration notes.

## Release checklist
1. Update tests for any contract additions.
2. Run `pytest -q`.
3. Update `CHANGELOG.md`.
4. Tag release (`vX.Y.Z`) and push tag.
5. Bump pinned version in app backend requirements.

## What not to do
- Don’t expose private internals as implicit API.
- Don’t change dataclass field names/order silently.
- Don’t ship behavior changes without changelog notes.
