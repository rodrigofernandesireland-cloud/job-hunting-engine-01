"""Stage 4: generate personalized outreach drafts."""

import os
from anthropic import Anthropic

import db

SYSTEM_PROMPT = """You write short, warm, specific cold outreach emails for a junior developer job search.
Under 150 words. Reference something specific from the job description or company.
Avoid buzzwords. Be confident but humble. End with a low-friction ask and an easy opt-out.
Output only the email body, with no subject or preamble."""


def build_user_prompt(config, company):
    candidate = config["candidate"]
    return f"""Candidate:
- Name: {candidate['name']}
- Location: {candidate['location']}
- Pitch: {candidate['pitch'].strip()}
- Portfolio: {candidate.get('portfolio_url', '')}

Target company: {company['name']}
Job title: {company['job_title']}
Job description: {(company['job_description'] or '')[:1500]}

Write the outreach email body now."""


def draft_email_body(client, config, company):
    response = client.messages.create(
        model=config["claude"]["model"], max_tokens=400,
        temperature=config["claude"].get("personalization_temperature", 0.7),
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(config, company)}],
    )
    return "\n".join(block.text for block in response.content if block.type == "text").strip()


def run(config):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env — cannot personalize.")
        return

    client = Anthropic(api_key=api_key)
    conn = db.get_connection()
    companies = db.get_companies_by_status(conn, "filtered_in")
    candidate = config["candidate"]
    signoff = config["outreach"]["signoff"].format(
        candidate_name=candidate["name"], candidate_linkedin=candidate.get("linkedin_url", "")
    )
    subject_template = config["outreach"]["subject_line"]
    drafted = 0

    for company in companies:
        contact = db.get_contact_for_company(conn, company["id"])
        if not contact or not contact["email"]:
            continue
        try:
            body = draft_email_body(client, config, company)
        except Exception as exc:
            print(f"Failed to draft for {company['name']}: {exc}")
            continue
        subject = subject_template.format(candidate_name=candidate["name"], candidate_location=candidate["location"])
        db.add_outreach_draft(conn, company["id"], contact["id"], subject, f"{body}\n\n{signoff}")
        db.update_company_status(conn, company["id"], "contacted")
        drafted += 1

    conn.close()
    print(f"Drafted {drafted} personalized emails. Run `python main.py review` to check them.")
