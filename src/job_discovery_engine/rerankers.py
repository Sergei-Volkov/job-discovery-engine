from __future__ import annotations

import json
import os
import ssl
import time
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from .models import JobMatch
    from .scoring import fit_label
except ImportError:  # pragma: no cover - script-mode fallback
    from models import JobMatch
    from scoring import fit_label


@dataclass
class LLMRerankReport:
    adjusted: int
    attempted: int
    planned_calls: int
    used_input_chars: int
    dry_run: bool
    warnings: list[str]


TRANSIENT_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}


def _extract_json_object(text: str) -> dict[str, object] | None:
    raw = (text or "").strip()
    if not raw:
        return None

    if raw.startswith("```"):
        lines = raw.splitlines()
        if len(lines) >= 3:
            raw = "\n".join(lines[1:-1]).strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    return payload


def _parse_adjustment_payload(payload: dict[str, object]) -> tuple[int, str] | None:
    expected = {"adjustment", "rationale"}
    if set(payload.keys()) != expected:
        return None

    adjustment_raw = payload.get("adjustment")
    rationale_raw = payload.get("rationale")
    if not isinstance(rationale_raw, str):
        return None

    try:
        adjustment = int(adjustment_raw)
    except (TypeError, ValueError):
        return None

    if adjustment < -3 or adjustment > 3:
        return None

    rationale = rationale_raw.strip()
    if not rationale:
        return None

    return adjustment, rationale


def _llm_adjustment(
    item: JobMatch,
    profile: str,
    api_base_url: str,
    api_key: str,
    model: str,
    timeout_seconds: int,
    max_description_chars: int,
) -> tuple[int, str] | None:
    endpoint = api_base_url.rstrip("/") + "/chat/completions"
    prompt = {
        "profile": profile,
        "role": item.title,
        "company": item.company,
        "source": item.source,
        "remote_policy": item.remote_policy,
        "base_score": item.score,
        "fit": item.fit,
        "matched_keywords": item.matched_keywords,
        "missing_skills": item.missing_skills,
        "fit_notes": item.fit_notes,
        "description": item.details_text[: max(200, max_description_chars)],
    }

    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 120,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict job-fit reranker. "
                    "Return JSON only with keys: adjustment (integer between -3 and 3), rationale (short string)."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Based on this job and candidate profile, suggest a conservative score adjustment. "
                    "Do not overfit. Prefer 0 unless evidence is clear.\n"
                    + json.dumps(prompt, ensure_ascii=True)
                ),
            },
        ],
    }

    request = Request(
        endpoint,
        method="POST",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout_seconds, context=context) as response:
        raw = json.loads(response.read().decode("utf-8", errors="ignore"))

    if not isinstance(raw, dict):
        return None
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first = choices[0]
    if not isinstance(first, dict):
        return None
    message = first.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None

    parsed = _extract_json_object(content)
    if not parsed:
        return None
    return _parse_adjustment_payload(parsed)


def apply_llm_reranker(
    matches: list[JobMatch],
    profile: str,
    enabled: bool,
    top_n: int,
    weight: float,
    model: str | None,
    api_base_url: str | None,
    dry_run: bool,
    max_calls: int,
    max_input_chars: int,
    max_retries: int,
    retry_backoff_seconds: float,
    timeout_seconds: int = 20,
) -> tuple[list[JobMatch], LLMRerankReport]:
    if not enabled or not matches:
        return matches, LLMRerankReport(adjusted=0, attempted=0, planned_calls=0, used_input_chars=0, dry_run=False, warnings=[])

    if top_n <= 0 or weight <= 0 or max_calls <= 0:
        return matches, LLMRerankReport(
            adjusted=0,
            attempted=0,
            planned_calls=0,
            used_input_chars=0,
            dry_run=dry_run,
            warnings=["LLM reranker skipped: top_n/weight/max_calls disabled"],
        )

    if max_input_chars <= 0:
        return matches, LLMRerankReport(
            adjusted=0,
            attempted=0,
            planned_calls=0,
            used_input_chars=0,
            dry_run=dry_run,
            warnings=["LLM reranker skipped: max_input_chars disabled"],
        )

    effective_max = min(top_n, max_calls, len(matches))

    if dry_run:
        planned_calls = 0
        used_input_chars = 0
        for item in matches[:effective_max]:
            remaining = max_input_chars - used_input_chars
            if remaining <= 0:
                break
            consume = min(len(item.details_text), min(4000, remaining))
            used_input_chars += max(0, consume)
            planned_calls += 1
        warnings = [
            "LLM reranker dry-run enabled: no external API requests were sent.",
            f"LLM reranker dry-run planned_calls={planned_calls}, used_input_chars={used_input_chars}",
        ]
        return matches, LLMRerankReport(
            adjusted=0,
            attempted=0,
            planned_calls=planned_calls,
            used_input_chars=used_input_chars,
            dry_run=True,
            warnings=warnings,
        )

    key = (os.environ.get("OPENAI_API_KEY", "") or os.environ.get("LLM_API_KEY", "")).strip()
    if not key:
        return matches, LLMRerankReport(
            adjusted=0,
            attempted=0,
            planned_calls=0,
            used_input_chars=0,
            dry_run=False,
            warnings=["LLM reranker skipped: API key missing"],
        )

    base_url = (api_base_url or os.environ.get("LLM_API_BASE_URL", "https://api.openai.com/v1")).strip()
    chosen_model = (model or os.environ.get("LLM_MODEL", "gpt-4o-mini")).strip()

    adjusted = 0
    attempted = 0
    warnings: list[str] = []
    reranked = list(matches)
    used_input_chars = 0
    planned_calls = 0

    for idx, item in enumerate(reranked[:effective_max]):
        # Approximate budget guardrail to cap token spend per run.
        details_budget = min(4000, max_input_chars - used_input_chars)
        if details_budget <= 0:
            warnings.append("LLM reranker budget reached: max_input_chars")
            break
        planned_calls += 1

        attempted += 1
        used_input_chars += min(len(item.details_text), details_budget)

        outcome: tuple[int, str] | None = None
        for retry in range(max(0, max_retries) + 1):
            try:
                outcome = _llm_adjustment(
                    item=item,
                    profile=profile,
                    api_base_url=base_url,
                    api_key=key,
                    model=chosen_model,
                    timeout_seconds=timeout_seconds,
                    max_description_chars=details_budget,
                )
                break
            except HTTPError as exc:
                status_code = int(getattr(exc, "code", 0) or 0)
                is_transient = status_code in TRANSIENT_HTTP_CODES
                if retry < max_retries and is_transient:
                    time.sleep(max(0.0, retry_backoff_seconds) * (2 ** retry))
                    continue
                warnings.append(f"LLM reranker warning for {item.company}/{item.title}: HTTP {status_code}")
                break
            except (URLError, TimeoutError) as exc:
                if retry < max_retries:
                    time.sleep(max(0.0, retry_backoff_seconds) * (2 ** retry))
                    continue
                warnings.append(f"LLM reranker warning for {item.company}/{item.title}: {type(exc).__name__}")
                break
            except Exception as exc:
                warnings.append(f"LLM reranker warning for {item.company}/{item.title}: {exc}")
                break

        if not outcome:
            continue

        delta_raw, rationale = outcome
        delta = int(round(delta_raw * weight))
        if delta == 0:
            continue

        new_score = max(0, item.score + delta)
        reranked[idx] = JobMatch(
            title=item.title,
            company=item.company,
            source=item.source,
            remote_policy=item.remote_policy,
            freshness=item.freshness,
            fit=fit_label(new_score),
            score=new_score,
            url=item.url,
            details_text=item.details_text,
            matched_keywords=item.matched_keywords,
            missing_skills=item.missing_skills,
            fit_notes=(item.fit_notes + f" LLM reranker: {rationale}").strip(),
        )
        adjusted += 1

    reranked = sorted(reranked, key=lambda row: (-row.score, row.freshness, row.title.lower()))
    return reranked, LLMRerankReport(
        adjusted=adjusted,
        attempted=attempted,
        planned_calls=planned_calls,
        used_input_chars=used_input_chars,
        dry_run=False,
        warnings=warnings,
    )
