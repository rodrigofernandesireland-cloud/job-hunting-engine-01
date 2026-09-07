"""Stage 7: FOLLOW UP."""

import os
from anthropic import Anthropic

import db

SYSTEM_PROMPT = """You write brief, low-pressure follow-up emails for a job search campaign.
Under 60 words. Do not guilt-trip or pressure. Output only the email body."""


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
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM outreach WHERE follow_up_of = ?", (original["id"],)
        ).fetchone()["c"]
        if existing >= max_follow_ups:
            continue

        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (original["contact_id"],)).fetchone()
        if not contact or not contact["email"] or contact["email_confidence"] is None:
            continue
        dnc = conn.execute(
            "SELECT 1 FROM outreach WHERE contact_id = ? AND status = 'do_not_contact' LIMIT 1",
            (contact["id"],),
        ).fetchone()
        if dnc:
            continue

        company = conn.execute("SELECT * FROM companies WHERE id = ?", (original["company_id"],)).fetchone()
        if not company:
            continue

        if client:
            try:
                response = client.messages.create(
                    model=config["claude"]["model"], max_tokens=200, temperature=0.6,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content":
                        f"Original email to {company['name']} for {company['job_title']}:\n\n{original['body']}\n\nWrite the follow-up."}],
                )
                body = "".join(b.text for b in response.content if b.type == "text").strip()
            except Exception as exc:
                print(f"Failed to draft follow-up for {company['name']}: {exc}")
                continue
        else:
            body = (f"Hi again — just following up on my note about the {company['job_title']} role. "
                    "Totally understand if the timing isn't right; let me know either way and I won't follow up again.")

        signoff = config["outreach"]["signoff"].format(
            candidate_name=config["candidate"]["name"],
            candidate_linkedin=config["candidate"].get("linkedin_url", ""),
        )
        new_id = db.add_outreach_draft(
            conn, company["id"], contact["id"], f"Re: {original['subject']}",
            f"{body}\n\n{signoff}", template_version="follow_up_v1",
        )
        conn.execute(
            "UPDATE outreach SET is_follow_up = 1, follow_up_of = ? WHERE id = ?",
            (original["id"], new_id),
        )
        conn.commit()
        drafted += 1

    conn.close()
    print(f"Drafted {drafted} follow-up emails. Run `python main.py review` to check them.")
