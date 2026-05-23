from __future__ import annotations

import json
import re
import ssl
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen


def fetch_json(
    url: str,
    timeout: int = 25,
    extra_headers: dict[str, str] | None = None,
) -> object:
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = Request(url, headers=headers)
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def fetch_text(url: str, timeout: int = 25) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        return response.read().decode("utf-8", errors="ignore")


def post_json(
    url: str,
    payload: dict[str, object],
    timeout: int = 25,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, object]:
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    context = ssl.create_default_context()
    with urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def normalize(text: object | None) -> str:
    return re.sub(r"\s+", " ", "" if text is None else str(text)).strip()


def normalize_url(url: str) -> str:
    raw = normalize(url)
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        query_items = [
            (k, v)
            for (k, v) in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
        ]
        normalized_query = urlencode(query_items, doseq=True)
        normalized_path = parts.path.rstrip("/") or "/"
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), normalized_path, normalized_query, ""))
    except Exception:
        return raw.rstrip("/")


def strip_latex(text: str) -> str:
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r" \1 ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?\{([^}]*)\}", r" \1 ", text)
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
    text = text.replace("\\\\", " ").replace("{", " ").replace("}", " ")
    return normalize(text)


def parse_date(raw: str | None) -> str:
    raw = normalize(raw)
    if not raw:
        return "n/a"

    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    if iso_match:
        return iso_match.group(0)

    if raw.isdigit() and len(raw) >= 10:
        try:
            return datetime.fromtimestamp(int(raw)).strftime("%Y-%m-%d")
        except Exception:
            pass

    try:
        return parsedate_to_datetime(raw).strftime("%Y-%m-%d")
    except Exception:
        return raw[:20]


def days_old(date_str: str) -> int | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str)
    if not match:
        return None
    try:
        then = datetime.strptime(match.group(1), "%Y-%m-%d")
        return (datetime.now() - then).days
    except Exception:
        return None


def parse_remote_policy(text: str) -> str:
    lower = text.lower()
    if "anywhere in the world" in lower or "worldwide" in lower:
        return "Worldwide"
    if "emea" in lower:
        return "EMEA"
    if "europe" in lower:
        return "Europe"
    if "north america" in lower or "us only" in lower or "usa only" in lower:
        return "US/North America"
    if "remote" in lower:
        return "Remote"
    return "Not stated"


def split_company_and_title(raw_title: str, fallback_company: str = "Unknown") -> tuple[str, str]:
    raw_title = normalize(raw_title)
    if not raw_title:
        return fallback_company, "Unknown role"

    if ":" in raw_title:
        company, title = raw_title.split(":", 1)
        return normalize(company), normalize(title)

    lower = raw_title.lower()
    if " at " in lower:
        idx = lower.rfind(" at ")
        title = raw_title[:idx]
        company = raw_title[idx + 4 :]
        return normalize(company), normalize(title)

    if " - " in raw_title:
        left, right = raw_title.split(" - ", 1)
        if any(term in left.lower() for term in ["engineer", "analytics", "etl", "airflow", "platform"]):
            return normalize(fallback_company), normalize(left)
        return normalize(left), normalize(right)

    return normalize(fallback_company), raw_title
