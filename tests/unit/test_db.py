import db


def test_database_schema_initializes(test_db):
    conn = db.get_connection()
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()

    assert {"companies", "contacts", "outreach", "replies"}.issubset(tables)


def test_company_job_url_is_unique(test_db):
    conn = db.get_connection()
    first = db.add_company(
        conn,
        "Example",
        "example.com",
        "test",
        "Junior Developer",
        "https://example.com/jobs/1",
        "A sufficiently detailed job description.",
        "Remote - Ireland",
        "python",
    )
    duplicate = db.add_company(
        conn,
        "Example",
        "example.com",
        "test",
        "Junior Developer",
        "https://example.com/jobs/1",
        "A sufficiently detailed job description.",
        "Remote - Ireland",
        "python",
    )
    conn.close()

    assert first is not None
    assert duplicate is None


def test_outreach_lifecycle(test_db):
    conn = db.get_connection()
    company_id = db.add_company(
        conn,
        "Example",
        "example.com",
        "test",
        "Junior Developer",
        "https://example.com/jobs/2",
        "A sufficiently detailed job description.",
        "Remote - Ireland",
        "python",
    )
    contact_id = db.add_contact(
        conn,
        company_id,
        "Test Recruiter",
        "Recruiter",
        "recruiter@example.com",
        "verified",
        "test",
    )
    outreach_id = db.add_outreach_draft(
        conn,
        company_id,
        contact_id,
        "Test subject",
        "Test body",
    )

    assert db.get_drafts(conn)[0]["id"] == outreach_id
    db.mark_sent(conn, outreach_id)
    assert db.get_approved(conn) == []
    sent = conn.execute("SELECT status, date_sent FROM outreach WHERE id = ?", (outreach_id,)).fetchone()
    conn.close()

    assert sent["status"] == "sent"
    assert sent["date_sent"] is not None
