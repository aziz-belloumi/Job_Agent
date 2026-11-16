"""Remotive job source fetcher and normalizer."""

import hashlib
from pathlib import Path
import time
from typing import Any

import requests
from rich.console import Console
import yaml

console = Console()


def load_config() -> dict[str, Any]:
    """Load configuration dictionary from config/sources.yaml."""
    config_path = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"
    if not config_path.exists():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def fetch() -> list[dict[str, Any]]:
    """Fetch and normalize jobs from Remotive API according to configuration."""
    cfg = load_config()
    remotive_cfg = cfg.get("remotive", {})

    if not remotive_cfg.get("enabled", False):
        return []

    api_url = remotive_cfg.get("api_url", "https://remotive.com/api/remote-jobs")
    keywords: list[str] = remotive_cfg.get("keywords", [])
    limit: int = remotive_cfg.get("limit_per_keyword", 50)

    results: list[dict[str, Any]] = []

    for idx, kw in enumerate(keywords):
        if idx > 0:
            time.sleep(1)  # Respect rate limit between requests

        try:
            r = requests.get(api_url, params={"search": kw, "limit": limit}, timeout=30)
            if r.status_code != 200:
                console.print(
                    f"[yellow]Warning: Remotive returned HTTP {r.status_code} for keyword '{kw}'.[/yellow]"
                )
                continue
            r.raise_for_status()
            data = r.json()
        except requests.RequestException as exc:
            console.print(
                f"[yellow]Warning: Remotive request failed for keyword '{kw}': {exc}[/yellow]"
            )
            continue

        for j in data.get("jobs", []):
            url = j.get("url", "")
            if not url:
                continue

            company = str(j.get("company_name") or "")
            title = str(j.get("title") or "")
            location = str(j.get("candidate_required_location") or "")
            raw_hash = f"{company}|{title}|{location}".lower().encode("utf-8")
            content_hash = hashlib.sha256(raw_hash).hexdigest()[:16]

            results.append({
                "source": "remotive",
                "source_url": url,
                "title": title,
                "company": company,
                "location": location,
                "employment_type": j.get("job_type"),
                "description": (j.get("description") or "")[:5000],
                "posted_at": j.get("publication_date"),
                "content_hash": content_hash,
            })

    return results
