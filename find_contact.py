"""Stage 3: identify a useful hiring contact."""

import os
import requests

import db

HUNTER_BASE = "https://api.hunter.io/v2"


def hunter_domain_search(domain, api_key, preferred_titles):
    try:
        resp = requests.get(
            f"{HUNTER_BASE}/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 10},
            timeout=15,
        )
        resp.raise_for_status()
        emails = resp.json().get("data", {}).get("emails", [])
    except Exception as exc:
        print(f"Hunter.io domain search failed for {domain}: {exc}")
        return None
    if not emails:
        return None

    for pref in preferred_titles:
        for item in emails:
            position = (item.get("position") or "").lower()
            if pref.lower() in position:
                return {
                    "name": f"{item.get('first_name', '')} {item.get('last_name', '')}".strip() or None,
                    "title": item.get("position"), "email": item.get("value"),
                    "confidence": "verified" if item.get("verification", {}).get("status") == "valid" else "guessed_high",
                }
    top = emails[0]
    return {
        "name": f"{top.get('first_name', '')} {top.get('last_name', '')}".strip() or None,
        "title": top.get("position"), "email": top.get("value"),
        "confidence": "verified" if top.get("verification", {}).get("status") == "valid" else "guessed_low",
    }


def pattern_guess_role_email(domain):
    if not domain:
        return None
    return {"name": None, "title": "Careers / Hiring Team", "email": f"careers@{domain}", "confidence": "guessed_low"}


def run(config):
    conn = db.get_connection()
    companies = db.get_companies_by_status(conn, "filtered_in")
    api_key = os.getenv("HUNTER_API_KEY")
    preferred_titles = config.get("contact_finding", {}).get("preferred_titles", [])
    found = fallback = skipped = 0

    for company in companies:
        contact = None
        if api_key and company["domain"]:
            contact = hunter_domain_search(company["domain"], api_key, preferred_titles)
            if contact:
                contact["source"] = "hunter"; found += 1
        if not contact and company["domain"]:
            contact = pattern_guess_role_email(company["domain"])
            fallback += 1
        if not contact:
            skipped += 1
            continue
        db.add_contact(conn, company["id"], contact["name"], contact["title"], contact["email"], contact["confidence"], contact["source"])

    conn.close()
    print(f"Contact search done. {found} via Hunter.io, {fallback} via pattern fallback, {skipped} skipped.")
