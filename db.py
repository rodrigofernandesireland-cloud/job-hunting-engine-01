"""SQLite database helpers."""

import sqlite3
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "pipeline.db"
SCHEMA_PATH = ROOT / "schema.sql"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with SCHEMA_PATH.open("r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def add_company(conn, name, domain, source, job_title, job_url, job_description, location, tags=""):
    try:
        cur = conn.execute(
            """INSERT INTO companies (name, domain, source, job_title, job_url, job_description, location, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (name, domain, source, job_title, job_url, job_description, location, tags),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_companies_by_status(conn, status):
    return conn.execute("SELECT * FROM companies WHERE status = ?", (status,)).fetchall()


def update_company_status(conn, company_id, status):
    conn.execute("UPDATE companies SET status = ? WHERE id = ?", (status, company_id))
    conn.commit()


def add_contact(conn, company_id, name, title, email, confidence, source):
    cur = conn.execute(
        """INSERT INTO contacts (company_id, name, title, email, email_confidence, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (company_id, name, title, email, confidence, source),
    )
    conn.commit()
    return cur.lastrowid


def get_contact_for_company(conn, company_id):
    return conn.execute(
        "SELECT * FROM contacts WHERE company_id = ? ORDER BY id DESC LIMIT 1", (company_id,)
    ).fetchone()


def add_outreach_draft(conn, company_id, contact_id, subject, body, template_version="v1"):
    tracking_id = uuid.uuid4().hex[:16]
    cur = conn.execute(
        """INSERT INTO outreach (company_id, contact_id, subject, body, template_version, tracking_id, status)
           VALUES (?, ?, ?, ?, ?, ?, 'draft')""",
        (company_id, contact_id, subject, body, template_version, tracking_id),
    )
    conn.commit()
    return cur.lastrowid


def get_drafts(conn):
    return conn.execute("SELECT * FROM outreach WHERE status = 'draft'").fetchall()


def get_approved(conn):
    return conn.execute("SELECT * FROM outreach WHERE status = 'approved'").fetchall()


def mark_sent(conn, outreach_id):
    conn.execute("UPDATE outreach SET status = 'sent', date_sent = datetime('now') WHERE id = ?", (outreach_id,))
    conn.commit()


def mark_opened(conn, tracking_id):
    conn.execute(
        """UPDATE outreach SET date_opened = COALESCE(date_opened, datetime('now')), open_count = open_count + 1
           WHERE tracking_id = ?""", (tracking_id,)
    )
    conn.commit()


def get_sent_outreach_needing_followup(conn, days_threshold):
    return conn.execute(
        """SELECT * FROM outreach
           WHERE status = 'sent'
             AND is_follow_up = 0
             AND date_sent <= datetime('now', ?)
             AND id NOT IN (SELECT COALESCE(follow_up_of, 0) FROM outreach WHERE is_follow_up = 1)
             AND id NOT IN (SELECT outreach_id FROM replies WHERE outreach_id IS NOT NULL)""",
        (f"-{int(days_threshold)} days",),
    ).fetchall()


def count_sent_today(conn):
    row = conn.execute("SELECT COUNT(*) AS c FROM outreach WHERE date(date_sent) = date('now')").fetchone()
    return row["c"] if row else 0


def add_reply(conn, outreach_id, from_email, subject, body):
    cur = conn.execute(
        "INSERT INTO replies (outreach_id, from_email, subject, body) VALUES (?, ?, ?, ?)",
        (outreach_id, from_email, subject, body),
    )
    conn.commit()
    return cur.lastrowid


def classify_reply(conn, reply_id, classification):
    conn.execute("UPDATE replies SET classification = ?, date_classified = datetime('now') WHERE id = ?", (classification, reply_id))
    conn.commit()


def get_unclassified_replies(conn):
    return conn.execute("SELECT * FROM replies WHERE classification IS NULL").fetchall()
