"""Stage 2: FILTER

Apply title, seniority, location and minimum-quality rules to new jobs.
"""

import re

import db


def _matches_any(text, terms):
    text = (text or "").lower()
    return any(term.lower() in text for term in terms if term)


def region_matches(location_text, target_regions, remote_only=False):
    location = (location_text or "").lower()
    regions = [r.lower() for r in target_regions]

    if remote_only and "remote" not in location:
        return False

    if not regions:
        return True

    return any(region in location for region in regions) or "remote" in location


def title_matches(title, wanted_titles, exclude_keywords):
    title_lower = (title or "").lower()
    if _matches_any(title_lower, exclude_keywords):
        return False

    if not wanted_titles:
        return True

    for wanted in wanted_titles:
        words = re.findall(r"[a-z0-9+#.]+", wanted.lower())
        if words and all(word in title_lower for word in words):
            return True
    return False


def run(config):
    conn = db.get_connection()
    new_jobs = db.get_companies_by_status(conn, "new")
    search = config.get("search", {})
    target_regions = search.get("target_regions", [])
    wanted_titles = search.get("job_titles", [])
    exclude_keywords = search.get("exclude_keywords", [])
    remote_only = bool(search.get("remote_only", False))

    kept, rejected = 0, 0
    for job in new_jobs:
        reasons = []

        if not title_matches(job["job_title"], wanted_titles, exclude_keywords):
            reasons.append("title does not match configured target roles")

        if not job["job_description"] or len(job["job_description"]) < 30:
            reasons.append("missing/too-short description")

        if not region_matches(job["location"], target_regions, remote_only):
            reasons.append(f"location '{job['location']}' not in target regions")

        if reasons:
            db.update_company_status(conn, job["id"], "filtered_out")
            rejected += 1
        else:
            db.update_company_status(conn, job["id"], "filtered_in")
            kept += 1

    conn.close()
    print(f"Filtered {len(new_jobs)} jobs: {kept} kept, {rejected} rejected.")
