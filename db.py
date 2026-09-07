"""Database connection and helper functions shared across all pipeline stages."""

import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "pipeline.db"
SCHEMA_PATH = Path(__file__).parent.parent / "database" / "schema.sql"


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


# ---------- Companies ----------

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
        return None  # job_url already exists, skip duplicate


def get_companies_by_status(conn, status):
    return conn.execute("SELECT * FROM companies WHERE status = ?", (status,)).fetchall()


def update_company_status(conn, company_id, status):
    conn.execute("UPDATE companies SET status = ? WHERE id = ?", (status, company_id))
    conn.commit()


# ---------- Contacts ----------

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


# ---------- Outreach ----------

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
    conn.execute(
        "UPDATE outreach SET status = 'sent', date_sent = datetime('now') WHERE id = ?",
        (outreach_id,),
    )
    conn.commit()


def mark_opened(conn, tracking_id):
    conn.execute(
        """UPDATE outreach
           SET date_opened = COALESCE(date_opened, datetime('now')),
               open_count = open_count + 1
           WHERE tracking_id = ?""",
        (tracking_id,),
    )
    conn.commit()


def get_sent_outreach_needing_followup(conn, days_threshold):
    return conn.execute(
        f"""SELECT * FROM outreach
            WHERE status = 'sent'
              AND is_follow_up = 0
              AND date_sent <= datetime('now', '-{int(days_threshold)} days')
              AND id NOT IN (SELECT COALESCE(follow_up_of, 0) FROM outreach WHERE is_follow_up = 1)
              AND id NOT IN (SELECT outreach_id FROM replies WHERE outreach_id IS NOT NULL)
         """
    ).fetchall()


def count_sent_today(conn):
    row = conn.execute(
        "SELECT COUNT(*) as c FROM outreach WHERE date(date_sent) = date('now')"
    ).fetchone()
    return row["c"] if row else 0


# ---------- Replies ----------

def add_reply(conn, outreach_id, from_email, subject, body):
    cur = conn.execute(
        """INSERT INTO replies (outreach_id, from_email, subject, body)
           VALUES (?, ?, ?, ?)""",
        (outreach_id, from_email, subject, body),
    )
    conn.commit()
    return cur.lastrowid


def classify_reply(conn, reply_id, classification):
    conn.execute(
        "UPDATE replies SET classification = ?, date_classified = datetime('now') WHERE id = ?",
        (classification, reply_id),
    )
    conn.commit()


def get_unclassified_replies(conn):
    return conn.execute("SELECT * FROM replies WHERE classification IS NULL").fetchall()