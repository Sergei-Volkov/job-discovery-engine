# Changelog

## 0.2.0
- `score_breakdown` sent as structured dict (score, fit, matched_keywords, missing_skills, fit_notes).
- `change_note` is human-readable: "updated on YYYY-MM-DD".
- `CollectionReport.sources` exposed on run result for per-source breakdown.
- SRE match profile added.
- Scoring unit tests added (44 tests).
- CI: discovery package workflow checks; pip-audit; coverage gate.

## 0.1.0
- Frozen public discovery contract.
- Extracted the current discovery pipeline into a standalone package.
- Added contract tests for the exported API and pipeline behavior.
