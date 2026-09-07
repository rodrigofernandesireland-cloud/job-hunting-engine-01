"""Reply polling and optional open-tracking server."""

import email
import imaplib
import os
from email.header import decode_header

from flask import Flask, Response

import db

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
    print(f"Tracking server running on {host}:{port}.")
    app.run(host=host, port=port)


def _decode(value):
    if value is None:
        return ""
    decoded = ""
    for text, enc in decode_header(value):
        decoded += text.decode(enc or "utf-8", errors="ignore") if isinstance(text, bytes) else text
    return decoded


def check_replies():
    """Poll the mailbox for replies from addresses already contacted."""
    imap_host = os.getenv("IMAP_HOST")
    imap_user = os.getenv("IMAP_USER")
    imap_password = os.getenv("IMAP_PASSWORD")
    imap_port = int(os.getenv("IMAP_PORT", 993))
    if not all([imap_host, imap_user, imap_password]):
        print("ERROR: IMAP credentials missing in .env.")
        return

    conn = db.get_connection()
    sent_rows = conn.execute(
        """SELECT o.id AS outreach_id, c.email AS contact_email
           FROM outreach o JOIN contacts c ON o.contact_id = c.id
           WHERE o.status = 'sent'"""
    ).fetchall()
    email_to_outreach = {r["contact_email"].lower(): r["outreach_id"] for r in sent_rows if r["contact_email"]}
    if not email_to_outreach:
        print("No sent outreach to check replies for yet.")
        conn.close()
        return

    mail = imaplib.IMAP4_SSL(imap_host, imap_port)
    mail.login(imap_user, imap_password)
    mail.select("INBOX")
    status, data = mail.search(None, "UNSEEN")
    if status != "OK":
        mail.logout()
        conn.close()
        print("IMAP search failed.")
        return

    new_replies = 0
    for num in data[0].split():
        status, msg_data = mail.fetch(num, "(RFC822)")
        if status != "OK":
            continue
        msg = email.message_from_bytes(msg_data[0][1])
        from_header = _decode(msg.get("From", ""))
        from_email = from_header.split("<")[-1].strip(">").lower() if "<" in from_header else from_header.lower()
        outreach_id = next((oid for addr, oid in email_to_outreach.items() if addr in from_email), None)
        if not outreach_id:
            continue

        subject = _decode(msg.get("Subject", ""))
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    body = payload.decode(errors="ignore") if payload else ""
                    break
        else:
            payload = msg.get_payload(decode=True)
            body = payload.decode(errors="ignore") if isinstance(payload, bytes) else str(payload or "")

        db.add_reply(conn, outreach_id, from_email, subject, body[:5000])
        new_replies += 1

    mail.logout()
    conn.close()
    print(f"Found {new_replies} new replies. Run `python main.py classify-replies` next.")
