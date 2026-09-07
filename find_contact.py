"""
Stage 3: IDENTIFY THE RIGHT PERSON
For each 'filtered_in' company, tries to find a real hiring contact.

Strategy (in order of preference):
  1. If Hunter.io API key is set, use their domain-search + email-finder
     endpoints to get a verified or high-confidence email for someone in
     a relevant role (recruiting/engineering/founder).
  2. Otherwise, fall back to pattern-guessing a role-based address
     (careers@, jobs@, hello@) at the company's domain — lower confidence
     but still a legitimate, publicly-intended inbox.

This deliberately does NOT scrape LinkedIn or any site that prohibits
scraping in its Terms of Service.
"""

import os
import requests

from . import db

HUNTER_BASE = "https://api.hunter.io/v2"


def hunter_domain_search(domain, api_key, preferred_titles):
    """Find people at a domain via Hunter.io, preferring relevant job titles."""
    try:
        resp = requests.get(
            f"{HUNTER_BASE}/domain-search",
            params={"domain": domain, "api_key": api_key, "limit": 10},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        emails = data.get("emails", [])
    except Exception as e:
        print(f"  Hunter.io domain search failed for {domain}: {e}")
        return None

    if not emails:
        return None

    # Prefer someone whose position matches our preferred titles
    for pref in preferred_titles:
        for e in emails:
            position = (e.get("position") or "").lower()
            if pref.lower() in position:
                return {
                    "name": f"{e.get('first_name', '')} {e.get('last_name', '')}".strip() or None,
                    "title": e.get("position"),
                    "email": e.get("value"),
                    "confidence": "verified" if e.get("verification", {}).get("status") == "valid" else "guessed_high",
                }

    # No preferred title matched — just take the top result
    top = emails[0]
    return {
        "name": f"{top.get('first_name', '')} {top.get('last_name', '')}".strip() or None,
        "title": top.get("position"),
        "email": top.get("value"),
        "confidence": "verified" if top.get("verification", {}).get("status") == "valid" else "guessed_low",
    }


def pattern_guess_role_email(domain):
    """Fallback: a role-based inbox is a reasonable, legitimate target."""
    if not domain:
        return None
    return {
        "name": None,
        "title": "Careers / Hiring Team",
        "email": f"careers@{domain}",
        "confidence": "guessed_low",
    }


def run(config):
    conn = db.get_connection()
    companies = db.get_companies_by_status(conn, "filtered_in")
    api_key = os.getenv("HUNTER_API_KEY")
    preferred_titles = config["contact_finding"].get("preferred_titles", [])

    found, fallback, skipped = 0, 0, 0

    for company in companies:
        contact = None

        if api_key and company["domain"]:
            contact = hunter_domain_search(company["domain"], api_key, preferred_titles)
            if contact:
                contact["source"] = "hunter"
                found += 1

        if not contact and company["domain"]:
            contact = pattern_guess_role_email(company["domain"])
            if contact:
                contact["source"] = "pattern_guess"
                fallback += 1

        if not contact:
            # No domain at all — can't guess an email. Leave it; you can fill
            # in a contact manually later via db.add_contact(), or revisit
            # once you have the company's site.
            skipped += 1
            continue

        db.add_contact(
            conn, company["id"], contact["name"], contact["title"],
            contact["email"], contact["confidence"], contact["source"],
        )

    conn.close()
    print(
        f"Contact search done. {found} via Hunter.io, {fallback} via pattern fallback, "
        f"{skipped} skipped (no domain available)."
    )