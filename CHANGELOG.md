# Changelog

## 0.3.0
- **Multi-format CV support**: `read_cv_text(cv_path)` auto-detects format.
  - `.pdf` → text extracted via `pypdf` (optional dep: `pip install 'job-discovery-engine[pdf]'`).
  - `.tex` → LaTeX markup stripped with `strip_latex`.
  - Any other extension → read as plain UTF-8 text.
  - `extract_owned_skills_from_cv` uses `read_cv_text` internally (no API change).
- **CV word-overlap semantic scoring**: `cv_word_bag(cv_text)` returns a `frozenset` of
  domain content words (alpha, len≥5, stop-words excluded) from the CV text.
  - `DiscoveryContext` gains a new optional `cv_words: frozenset[str]` field (default `frozenset()`).
  - `score_match()` adds up to +2 points when the job description contains words from `cv_words`
    (1 point per 5 overlapping content words, capped at 2).
  - `run_discovery_pipeline` computes `cv_words` from the CV file and populates the context automatically.
- New public symbols: `read_cv_text` (text_utils), `cv_word_bag` (scoring), both re-exported from `shared`.
- Optional dependency `[pdf]` added to `pyproject.toml`.
- 13 new contract tests covering `read_cv_text`, `cv_word_bag`, and semantic scoring.

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
