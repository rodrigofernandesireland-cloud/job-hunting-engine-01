"""
Stage 7: FOLLOW UP
Finds outreach that was sent N+ days ago, got no reply, and hasn't already
been followed up (respecting max_follow_ups from config). Drafts a short,
low-pressure follow-up using Claude and queues it as a new draft — it goes
through the same review/approve/send flow as original outreach.
"""

import os
from anthropic import Anthropic

from . import db

SYSTEM_PROMPT = """You write brief, low-pressure follow-up emails for a job \
search campaign. Rules:
- Under 60 words.
- Reference that this is a gentle follow-up to a previous email, don't repeat the whole pitch.
- No guilt-tripping or pressure ("just circling back", "quick bump", etc. are fine).
- Assume they're busy; make it effortless for them to reply or ignore.
- Output ONLY the email body text."""


def run(config):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    conn = db.get_connection()
    days_threshold = config["outreach"].get("follow_up_after_days", 5)
    max_follow_ups = config["outreach"].get("max_follow_ups", 1)

    candidates = db.get_sent_outreach_needing_followup(conn, days_threshold)

    if not candidates:
        print("No outreach currently needs a follow-up.")
        conn.close()
        return

    client = Anthropic(api_key=api_key) if api_key else None
    drafted = 0

    for original in candidates:
        # Respect max_follow_ups: count existing follow-ups of this original
        existing_followups = conn.execute(
            "SELECT COUNT(*) as c FROM outreach WHERE follow_up_of = ?", (original["id"],)
        ).fetchone()["c"]
        if existing_followups >= max_follow_ups:
            continue

        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (original["contact_id"],)).fetchone()
        if not contact or contact["email_confidence"] is None:
            continue
        # Skip anyone who unsubscribed
        dnc = conn.execute(
            "SELECT 1 FROM outreach WHERE contact_id = ? AND status = 'do_not_contact'",
            (contact["id"],),
        ).fetchone()
        if dnc:
            continue

        company = conn.execute("SELECT * FROM companies WHERE id = ?", (original["company_id"],)).fetchone()

        if client:
            try:
                response = client.messages.create(
                    model=config["claude"]["model"],
                    max_tokens=200,
                    temperature=0.6,
                    system=SYSTEM_PROMPT,
                    messages=[{
                        "role": "user",
                        "content": f"Original email sent to {company['name']} for the "
                                   f"{company['job_title']} role:\n\n{original['body']}\n\n"
                                   f"Write the follow-up now.",
                    }],
                )
                body = "".join(b.text for b in response.content if b.type == "text").strip()
            except Exception as e:
                print(f"  Failed to draft follow-up for {company['name']}: {e}")
                continue
        else:
            body = (
                f"Hi again — just following up on my note about the {company['job_title']} "
                f"role. Totally understand if the timing isn't right; let me know either way "
                f"and I won't follow up again."
            )

        signoff = config["outreach"]["signoff"].format(
            candidate_name=config["candidate"]["name"],
            candidate_linkedin=config["candidate"].get("linkedin_url", ""),
        )
        full_body = f"{body}\n\n{signoff}"
        subject = f"Re: {original['subject']}"

        new_id = db.add_outreach_draft(conn, company["id"], contact["id"], subject, full_body, template_version="follow_up_v1")
        conn.execute(
            "UPDATE outreach SET is_follow_up = 1, follow_up_of = ? WHERE id = ?",
            (original["id"], new_id),
        )
        conn.commit()
        drafted += 1

    conn.close()
    print(f"Drafted {drafted} follow-up emails. Run `python main.py review` to check them.")