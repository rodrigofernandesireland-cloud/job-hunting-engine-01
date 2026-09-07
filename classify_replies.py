"""
Stage 8: CLASSIFY RESPONSES
Uses Claude to read each unclassified reply and tag it as one of:
  interested / not_interested / auto_reply / needs_human / unsubscribe

This lets you triage your inbox fast: jump straight to 'interested' replies,
ignore auto-replies, and honor unsubscribe requests (stops all future
follow-ups to that contact).
"""

import os
from anthropic import Anthropic

from . import db

VALID_LABELS = {"interested", "not_interested", "auto_reply", "needs_human", "unsubscribe"}

SYSTEM_PROMPT = """You classify email replies to a job-search outreach campaign. \
Read the reply and respond with EXACTLY ONE WORD from this list, nothing else:

interested       - they want to talk further, see a CV, or schedule something
not_interested   - a polite decline, no current openings, "we'll keep you on file", etc.
auto_reply       - out-of-office, autoresponder, "no longer at this address", etc.
needs_human      - anything ambiguous, a question you can't safely auto-answer, or unusual
unsubscribe      - they explicitly ask not to be contacted again

Respond with only the single label word."""


def classify_one(client, config, reply_body):
    response = client.messages.create(
        model=config["claude"]["model"],
        max_tokens=10,
        temperature=0,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": reply_body[:3000]}],
    )
    text = "".join(block.text for block in response.content if block.type == "text").strip().lower()
    return text if text in VALID_LABELS else "needs_human"


def run(config):
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env — cannot classify replies.")
        return

    client = Anthropic(api_key=api_key)
    conn = db.get_connection()
    unclassified = db.get_unclassified_replies(conn)

    if not unclassified:
        print("No unclassified replies.")
        conn.close()
        return

    counts = {}
    for reply in unclassified:
        label = classify_one(client, config, reply["body"] or reply["subject"] or "")
        db.classify_reply(conn, reply["id"], label)
        counts[label] = counts.get(label, 0) + 1

        if label == "unsubscribe":
            # Prevent any future follow-ups to this contact
            conn.execute(
                """UPDATE outreach SET status = 'do_not_contact'
                   WHERE contact_id = (
                       SELECT contact_id FROM outreach WHERE id = ?
                   )""",
                (reply["outreach_id"],),
            )
            conn.commit()

    conn.close()
    print(f"Classified {len(unclassified)} replies: {counts}")
    if counts.get("interested"):
        print(f"\n{counts['interested']} INTERESTED replies — check these first! "
              f"Query: SELECT * FROM replies WHERE classification='interested';")