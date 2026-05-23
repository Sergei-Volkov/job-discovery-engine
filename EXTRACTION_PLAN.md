# Discovery Extraction Plan

This file is the short version: enough detail to start the split, not a full implementation spec.

## Current state
- Discovery already has a public API in `discovery/api.py`.
- Orchestration is in `discovery/pipeline.py`.
- Runtime state is explicit via `DiscoveryContext`.
- The app can run discovery in `subprocess` or `module` mode.

## Recommended split
- Keep `job-application-insights` as the app/product repo.
- Create a separate Python package repo for discovery, for example `job-discovery-engine`.
- The app should depend on a pinned release of that package.
- The app should only rely on the public API: `DiscoveryContext`, `DiscoveryRunOptions`, `DiscoveryRunResult`, `DiscoveryRunWarnings`, `run_discovery_pipeline`.

## First release contract (`0.1.0`)
- Stable inputs: required CV path, current profile values, bounded numeric controls, current source keys.
- Stable outputs: strict shortlist, broad results, file paths, counts, warnings.
- Compatibility rule: patch fixes only, minor adds fields/options, major breaks the contract.
- Avoid importing private discovery internals from the app.

## Minimal extraction order
1. Freeze the public discovery contract and test it.
2. Move discovery code into the new package repo and add package metadata.
3. Move discovery tests with it.
4. Publish `0.1.0` and pin the app to it.
5. Keep `subprocess` as the fallback runner while validating the package.
6. Flip to `module` mode after the package proves stable.

## What not to do
- Don’t split before the public API is stable.
- Don’t keep the app importing discovery internals.
- Don’t let hidden globals become part of the contract.
