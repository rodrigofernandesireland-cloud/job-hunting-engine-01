"""
Stage 4: PERSONALIZE
Uses the Claude API to draft a short, genuinely personalized outreach email
for each company that has a contact identified. Drafts are saved with
status='draft' so you can review them (Stage: `review`) before sending.
"""

import os
from anthropic import Anthropic

from . import db

SYSTEM_PROMPT = """You write short, warm, specific cold outreach emails for a junior \
developer job search. Rules:

- Under 150 words.
- Reference something SPECIFIC from the job description or company (not generic flattery).
- No buzzwords like "passionate", "synergy", "rockstar", "ninja".
- Confident but humble tone — a real junior dev, not a marketer.
- End with a clear, low-friction ask (a quick chat, or just "happy to send my CV").
- Include one line offering an easy opt-out (e.g. "let me know if this isn't relevant \
and I won't follow up").
- Output ONLY the email body text. No subject line, no markdown, no preamble."""


def build_user_prompt(config, company):
    candidate = config["candidate"]
    return f"""Candidate:
- Name: {candidate['name']}
- Location: {candidate['location']}
- Pitch: {candidate['pitch'].strip()}
- Portfolio: {candidate.get('portfolio_url', '')}

Target company: {company['name']}
Job title they're hiring for: {company['job_title']}
Job description excerpt: {(company['job_description'] or '')[:1500]}

Write the outreach email body now."""


def draft_email_body(client, config, company):
    response = client.messages.create(
        model=config["claude"]["model"],
        max_tokens=400,
        temperature=config["claude"].get("personalization_temperature", 0.7),
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(config, company)}],
    )
    text_parts = [block.text for block in response.content if block.type == "text"]
    return "\n".join(text_parts).strip()


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
        candidate_name=candidate["name"],
        candidate_linkedin=candidate.get("linkedin_url", ""),
    )
    subject_template = config["outreach"]["subject_line"]

    drafted = 0
    for company in companies:
        contact = db.get_contact_for_company(conn, company["id"])
        if not contact or not contact["email"]:
            continue  # no contact yet — run find-contacts first

        try:
            body = draft_email_body(client, config, company)
        except Exception as e:
            print(f"  Failed to draft for {company['name']}: {e}")
            continue

        full_body = f"{body}\n\n{signoff}"
        subject = subject_template.format(
            candidate_name=candidate["name"],
            candidate_location=candidate["location"],
        )

        db.add_outreach_draft(conn, company["id"], contact["id"], subject, full_body)
        db.update_company_status(conn, company["id"], "contacted")  # marks "in outreach pipeline"
        drafted += 1

    conn.close()
    print(f"Drafted {drafted} personalized emails. Run `python main.py review` to check them.")