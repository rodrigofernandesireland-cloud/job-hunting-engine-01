"""Stage 1: FETCH

Fetch jobs from public job-board APIs, normalize them to one internal shape,
and store them in SQLite. No API keys are required for the default sources.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

import requests

import db

REMOTEOK_URL = "https://remoteok.com/api"
ARBEITNOW_URL = "https://www.arbeitnow.com/api/job-board-api"
TIMEOUT = 20
USER_AGENT = "job-hunting-engine/1.0"


def _domain_from_url(url):
    if not url:
        return None
    try:
        host = urlparse(url).hostname or ""
        host = host.lower().removeprefix("www.")
        return host or None
    except Exception:
        return None


def _clean_text(value):
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _job_key(job):
    external_id = job.get("external_id")
    if external_id:
        return f"{job['source']}:{external_id}"
    raw = "|".join([
        job.get("source", ""),
        job.get("company_name", ""),
        job.get("title", ""),
        job.get("url", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _request_json(url, params=None):
    response = requests.get(
        url,
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fetch_remoteok():
    """Fetch public RemoteOK listings."""
    data = _request_json(REMOTEOK_URL)
    jobs = []

    # RemoteOK returns metadata objects before the actual job records.
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or not item.get("position"):
            continue

        company_url = item.get("company_url") or item.get("company_url")
        jobs.append({
            "source": "remoteok",
            "external_id": str(item.get("id") or item.get("slug") or ""),
            "title": _clean_text(item.get("position")),
            "company_name": _clean_text(item.get("company")),
            "company_domain": _domain_from_url(company_url),
            "location": _clean_text(item.get("location")),
            "url": item.get("url") or "",
            "description": _clean_text(item.get("description")),
            "posted_at": item.get("date"),
            "tags": item.get("tags") or [],
        })
    return jobs


def fetch_arbeitnow():
    """Fetch public Arbeitnow job-board listings."""
    data = _request_json(ARBEITNOW_URL)
    jobs = []

    for item in (data.get("data", []) if isinstance(data, dict) else []):
        if not isinstance(item, dict) or not item.get("title"):
            continue

        company_url = item.get("company_url") or ""
        jobs.append({
            "source": "arbeitnow",
            "external_id": str(item.get("slug") or item.get("id") or ""),
            "title": _clean_text(item.get("title")),
            "company_name": _clean_text(item.get("company_name")),
            "company_domain": _domain_from_url(company_url),
            "location": _clean_text(item.get("location")),
            "url": item.get("url") or "",
            "description": _clean_text(item.get("description")),
            "posted_at": item.get("created_at"),
            "tags": item.get("tags") or [],
        })
    return jobs


def normalize_jobs(jobs):
    normalized = []
    seen = set()

    for job in jobs:
        job = dict(job)
        job["title"] = _clean_text(job.get("title"))
        job["company_name"] = _clean_text(job.get("company_name")) or "Unknown company"
        job["description"] = _clean_text(job.get("description"))
        job["location"] = _clean_text(job.get("location")) or "Remote"
        job["url"] = job.get("url") or ""
        job["tags"] = job.get("tags") or []
        if isinstance(job["tags"], str):
            job["tags"] = [x.strip() for x in job["tags"].split(",") if x.strip()]
        job["company_domain"] = job.get("company_domain") or _domain_from_url(job.get("url"))

        if not job["title"] or not job["url"] or not job["description"]:
            continue

        key = _job_key(job)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(job)

    return normalized


def save_jobs(jobs):
    conn = db.get_connection()
    inserted = 0

    for job in jobs:
        company_id = db.add_company(
            conn,
            name=job["company_name"],
            domain=job.get("company_domain"),
            source=job["source"],
            job_title=job["title"],
            job_url=job["url"],
            job_description=job["description"],
            location=job.get("location"),
            tags=", ".join(job.get("tags", [])),
        )
        if company_id is not None:
            inserted += 1

    conn.close()
    return inserted


def run(config):
    sources = config.get("search", {}).get("sources", {})
    jobs = []
    failures = []

    if sources.get("remoteok", True):
        try:
            jobs.extend(fetch_remoteok())
        except Exception as exc:
            failures.append(f"RemoteOK: {exc}")

    if sources.get("arbeitnow", True):
        try:
            jobs.extend(fetch_arbeitnow())
        except Exception as exc:
            failures.append(f"Arbeitnow: {exc}")

    jobs = normalize_jobs(jobs)
    inserted = save_jobs(jobs)

    print(f"Fetched {len(jobs)} normalized jobs; inserted {inserted} new jobs.")
    for failure in failures:
        print(f"WARNING: {failure}")

    if not jobs and failures:
        print("No jobs were fetched. Check internet access and the configured sources.")

    return inserted
