"""Stage 5: SEND

Send approved outreach emails via SMTP, respecting daily limits and the
configured send window. Open tracking is optional and can be disabled by
omitting TRACKING_BASE_URL.
"""

import os
import time
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import db


def within_send_window(config):
    start_hour, end_hour = config["outreach"].get("send_window_hours", [0, 24])
    now_hour = datetime.now().hour
    return start_hour <= now_hour < end_hour


def build_message(config, outreach_row, contact_row, from_email):
    tracking_base = os.getenv("TRACKING_BASE_URL")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = outreach_row["subject"]
    msg["From"] = from_email
    msg["To"] = contact_row["email"]

    msg.attach(MIMEText(outreach_row["body"], "plain"))

    if tracking_base:
        tracking_base = tracking_base.rstrip("/")
        pixel_url = f"{tracking_base}/track/{outreach_row['tracking_id']}.png"
        html_body = outreach_row["body"].replace("\n", "<br>") + (
            f'<img src="{pixel_url}" width="1" height="1" style="display:none">'
        )
        msg.attach(MIMEText(html_body, "html"))

    return msg


def run(config, dry_run=False):
    conn = db.get_connection()

    already_sent_today = db.count_sent_today(conn)
    daily_limit = config["outreach"].get("daily_send_limit", 25)
    remaining = daily_limit - already_sent_today

    if remaining <= 0:
        print(f"Daily send limit ({daily_limit}) already reached today. Try again tomorrow.")
        conn.close()
        return

    if not within_send_window(config) and not dry_run:
        print("Outside configured send window. Skipping.")
        conn.close()
        return

    to_send = db.get_approved(conn)[:remaining]
    if not to_send:
        print("No approved drafts to send. Run `python main.py review` first.")
        conn.close()
        return

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not dry_run and not all([smtp_host, smtp_user, smtp_password]):
        print("ERROR: SMTP credentials missing in .env. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD.")
        conn.close()
        return

    server = None
    if not dry_run:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        server.starttls()
        server.login(smtp_user, smtp_password)

    sent = 0
    for outreach_row in to_send:
        contact_row = conn.execute(
            "SELECT * FROM contacts WHERE id = ?", (outreach_row["contact_id"],)
        ).fetchone()
        if not contact_row or not contact_row["email"]:
            continue

        msg = build_message(config, outreach_row, contact_row, smtp_user or "you@example.com")

        if dry_run:
            print(f"[DRY RUN] Would send to {contact_row['email']}: {outreach_row['subject']}")
        else:
            try:
                server.sendmail(smtp_user, contact_row["email"], msg.as_string())
                db.mark_sent(conn, outreach_row["id"])
                print(f"Sent to {contact_row['email']} ({outreach_row['subject']})")
                sent += 1
                time.sleep(3)
            except Exception as e:
                print(f"  Failed to send to {contact_row['email']}: {e}")
                conn.execute("UPDATE outreach SET status = 'failed' WHERE id = ?", (outreach_row["id"],))
                conn.commit()

    if server:
        server.quit()
    conn.close()
    print(f"\nDone. Sent {sent} emails ({daily_limit - already_sent_today - sent} of today's cap remaining).")
