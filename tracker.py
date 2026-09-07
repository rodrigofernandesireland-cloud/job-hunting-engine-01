"""
Stage 6: TRACK
Two pieces:
  1. `serve()` — a tiny Flask server that serves the 1x1 tracking pixel
     referenced in each sent email and logs opens to the database. Run
     this continuously (e.g. `python main.py track-server`) somewhere
     reachable at TRACKING_BASE_URL (use ngrok or a small VPS if you
     want it to work outside your laptop).
  2. `check_replies()` — polls your inbox via IMAP for new messages from
     addresses you've contacted, and logs them as replies (unclassified —
     Stage 8 handles classification).
"""

import os
import email
import imaplib
from email.header import decode_header

from flask import Flask, Response
from . import db

# 1x1 transparent PNG, hardcoded
PIXEL_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n\x2d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)

app = Flask(__name__)


@app.route("/track/<tracking_id>.png")
def track_open(tracking_id):
    conn = db.get_connection()
    db.mark_opened(conn, tracking_id)
    conn.close()
    return Response(PIXEL_BYTES, mimetype="image/png")


def serve(host="0.0.0.0", port=5000):
    print(f"Tracking server running on {host}:{port}. Set TRACKING_BASE_URL accordingly in .env.")
    app.run(host=host, port=port)


def _decode(value):
    if value is None:
        return ""
    parts = decode_header(value)
    decoded = ""
    for text, enc in parts:
        if isinstance(text, bytes):
            decoded += text.decode(enc or "utf-8", errors="ignore")
        else:
            decoded += text
    return decoded


def check_replies():
    """Poll the inbox for replies from addresses we've emailed, log them unclassified."""
    imap_host = os.getenv("IMAP_HOST")
    imap_user = os.getenv("IMAP_USER")
    imap_password = os.getenv("IMAP_PASSWORD")
    imap_port = int(os.getenv("IMAP_PORT", 993))

    if not all([imap_host, imap_user, imap_password]):
        print("ERROR: IMAP credentials missing in .env. Set IMAP_HOST/IMAP_USER/IMAP_PASSWORD.")
        return

    conn = db.get_connection()
    sent_rows = conn.execute(
        """SELECT o.id as outreach_id, c.email as contact_email
           FROM outreach o JOIN contacts c ON o.contact_id = c.id
           WHERE o.status = 'sent'"""
    ).fetchall()
    email_to_outreach = {row["contact_email"].lower(): row["outreach_id"] for row in sent_rows if row["contact_email"]}

    if not email_to_outreach:
        print("No sent outreach to check replies for yet.")
        conn.close()
        return

    mail = imaplib.IMAP4_SSL(imap_host, imap_port)
    mail.login(imap_user, imap_password)
    mail.select("INBOX")

    status, data = mail.search(None, "UNSEEN")
    if status != "OK":
        print("IMAP search failed.")
        mail.logout()
        conn.close()
        return

    new_replies = 0
    for num in data[0].split():
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        from_header = _decode(msg.get("From", ""))
        from_email = from_header.split("<")[-1].strip(">").lower() if "<" in from_header else from_header.lower()

        matched_outreach_id = None
        for known_email, outreach_id in email_to_outreach.items():
            if known_email in from_email:
                matched_outreach_id = outreach_id
                break

        if not matched_outreach_id:
            continue  # not a reply to one of our sent emails

        subject = _decode(msg.get("Subject", ""))
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body = part.get_payload(decode=True).decode(errors="ignore")
                    except Exception:
                        pass
                    break
        else:
            try:
                body = msg.get_payload(decode=True).decode(errors="ignore")
            except Exception:
                body = str(msg.get_payload())

        db.add_reply(conn, matched_outreach_id, from_email, subject, body[:5000])
        new_replies += 1

    mail.logout()
    conn.close()
    print(f"Found {new_replies} new replies. Run `python main.py classify-replies` next.")