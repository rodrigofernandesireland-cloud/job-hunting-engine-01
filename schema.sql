-- Job Hunting Engine — database schema

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT,
    source TEXT,                    -- remoteok / arbeitnow / weworkremotely / adzuna / manual
    job_title TEXT,
    job_url TEXT UNIQUE,
    job_description TEXT,
    location TEXT,
    tags TEXT,                      -- comma-separated
    date_found TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'new'       -- new / filtered_in / filtered_out / contacted / done
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    name TEXT,
    title TEXT,
    email TEXT,
    email_confidence TEXT,          -- verified / guessed_high / guessed_low
    source TEXT,                    -- hunter / pattern_guess / listing / manual
    date_found TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS outreach (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id),
    contact_id INTEGER REFERENCES contacts(id),
    subject TEXT,
    body TEXT,
    template_version TEXT,
    status TEXT DEFAULT 'draft',    -- draft / approved / sent / failed
    tracking_id TEXT UNIQUE,        -- used in the open-tracking pixel URL
    date_drafted TEXT DEFAULT (datetime('now')),
    date_sent TEXT,
    date_opened TEXT,
    open_count INTEGER DEFAULT 0,
    is_follow_up INTEGER DEFAULT 0,
    follow_up_of INTEGER REFERENCES outreach(id)
);

CREATE TABLE IF NOT EXISTS replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outreach_id INTEGER REFERENCES outreach(id),
    from_email TEXT,
    subject TEXT,
    body TEXT,
    classification TEXT,            -- interested / not_interested / auto_reply / needs_human / unsubscribe
    date_received TEXT DEFAULT (datetime('now')),
    date_classified TEXT
);

CREATE INDEX IF NOT EXISTS idx_companies_status ON companies(status);
CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach(status);
CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);