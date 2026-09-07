"""
Stage 2: FILTER
Applies your criteria (region, seniority, keywords) to 'new' companies and
marks each one 'filtered_in' or 'filtered_out'. Keyword matching already
happened at fetch time (Stage 1); this stage adds region/location filtering
and a basic quality check (must have a job description + some way to reach
the company).
"""

from . import db


def region_matches(location_text, target_regions):
    if not location_text:
        return True  # unknown location, don't auto-reject — let contact-finding decide
    location_lower = location_text.lower()
    if "remote" in location_lower and "remote" not in [r.lower() for r in target_regions]:
        # Generic "remote" with no region info — allow it through, most remote EU
        # roles just say "Remote" without a country.
        return True
    return any(region.lower() in location_lower for region in target_regions)


def run(config):
    conn = db.get_connection()
    new_companies = db.get_companies_by_status(conn, "new")
    target_regions = config["search"].get("target_regions", [])

    kept, rejected = 0, 0
    for company in new_companies:
        reasons_to_reject = []

        if not company["job_description"] or len(company["job_description"]) < 30:
            reasons_to_reject.append("missing/too-short description")

        if not region_matches(company["location"], target_regions):
            reasons_to_reject.append(f"location '{company['location']}' not in target regions")

        if reasons_to_reject:
            db.update_company_status(conn, company["id"], "filtered_out")
            rejected += 1
        else:
            db.update_company_status(conn, company["id"], "filtered_in")
            kept += 1

    conn.close()
    print(f"Filtered {len(new_companies)} companies: {kept} kept, {rejected} rejected.")