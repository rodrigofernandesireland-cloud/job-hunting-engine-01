"""Review and approve generated outreach drafts."""

import db


def run(config, auto_approve=False):
    conn = db.get_connection()
    drafts = db.get_drafts(conn)

    if not drafts:
        print("No drafts waiting for review.")
        conn.close()
        return

    if auto_approve:
        for d in drafts:
            conn.execute("UPDATE outreach SET status = 'approved' WHERE id = ?", (d["id"],))
        conn.commit()
        conn.close()
        print(f"Auto-approved {len(drafts)} drafts.")
        return

    print(f"\n{len(drafts)} drafts waiting for review.\n" + "=" * 60)
    for d in drafts:
        company = conn.execute("SELECT * FROM companies WHERE id = ?", (d["company_id"],)).fetchone()
        contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (d["contact_id"],)).fetchone()

        print(f"\n[Draft #{d['id']}] -> {company['name']} ({company['job_title']})")
        print(f"To: {contact['email']} (confidence: {contact['email_confidence']})")
        print(f"Subject: {d['subject']}")
        print("-" * 40)
        print(d["body"])
        print("=" * 60)

        choice = input("Approve (a) / Skip (s) / Reject-and-delete (r) / Quit review (q): ").strip().lower()
        if choice == "a":
            conn.execute("UPDATE outreach SET status = 'approved' WHERE id = ?", (d["id"],))
            conn.commit()
        elif choice == "r":
            conn.execute("DELETE FROM outreach WHERE id = ?", (d["id"],))
            conn.commit()
        elif choice == "q":
            break

    conn.close()
