"""Stage 8: classify incoming replies with Claude."""

import os
from anthropic import Anthropic

import db

VALID_LABELS = {"interested", "not_interested", "auto_reply", "needs_human", "unsubscribe"}

SYSTEM_PROMPT = """Classify a job-search email reply. Respond with exactly one label:
interested, not_interested, auto_reply, needs_human, unsubscribe.
Use needs_human for ambiguity. Use unsubscribe only for an explicit request not to be contacted again."""


def classify_one(client, config, reply_body):
    response = client.messages.create(
        model=config["claude"]["model"], max_tokens=10, temperature=0,
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
        if label == "unsubscribe" and reply["outreach_id"]:
            conn.execute(
                """UPDATE outreach SET status = 'do_not_contact'
                   WHERE contact_id = (SELECT contact_id FROM outreach WHERE id = ?)""",
                (reply["outreach_id"],),
            )
            conn.commit()

    conn.close()
    print(f"Classified {len(unclassified)} replies: {counts}")
