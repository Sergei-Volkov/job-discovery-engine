# Discovery API Contract

This is the stable public contract for the discovery package while it remains inside the app repo and after it is extracted.

## Frozen public surface
- `DiscoveryContext`
- `DiscoveryRunOptions`
- `DiscoveryRunResult`
- `DiscoveryRunWarnings`
- `run_discovery_pipeline(options)`

## Stability rules
- Patch releases may fix behavior without changing the public contract.
- Minor releases may add fields or optional parameters with defaults.
- Major releases may change or remove public fields, names, or semantics.
- App code must not import discovery internals directly.

## Compatibility expectations
- `DiscoveryRunOptions` keeps the current required/optional meaning of its fields.
- `DiscoveryRunResult` keeps the current result categories: context, matches, reports, file paths, and sync counts.
- `DiscoveryContext` remains the input bundle for profile and skill context.