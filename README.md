# Job Hunting Engine

Local-first job-search assistant. The production flow is deliberately separate from the test flow:

`jobs -> filter -> contact -> draft -> review -> send -> replies`

## Repository layout

```text
.
├── main.py                 # functional CLI / orchestration
├── db.py                   # SQLite persistence
├── fetch_jobs.py           # RemoteOK + Arbeitnow adapters
├── find_companies.py       # deterministic job filtering
├── find_contact.py         # optional Hunter lookup + role inbox fallback
├── personalize.py          # Claude drafting
├── review.py               # human approval gate
├── send_email.py           # SMTP delivery / dry-run
├── tracker.py              # IMAP replies + optional tracking pixel
├── follow_up.py
├── classify_replies.py
├── schema.sql
├── config.example.yaml
├── .env.example
├── tests/
│   ├── unit/               # fast, isolated tests; no network
│   ├── integration/        # multiple modules, still offline
│   └── functional/         # real CLI with isolated DB
└── data/                   # local runtime data, ignored by git
```

## Setup

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements-dev.txt
cp .env.example .env
cp config.example.yaml config.yaml
```

`config.yaml` contains your profile and search behaviour. `.env` contains secrets and mailbox credentials. Neither should be committed.

## Testing strategy

Normal tests never call live job APIs, Claude, Hunter, SMTP or IMAP.

```bash
# Fast isolated tests
pytest tests/unit

# Offline multi-component tests
pytest tests/integration

# CLI smoke tests using a temporary database
pytest tests/functional

# CI/default suite
pytest -m "not live"
```

Unit tests mock HTTP responses and use temporary SQLite databases. Integration tests exercise multiple modules with fake payloads. Functional tests execute `main.py` as a subprocess while `JOB_ENGINE_DB_PATH` points to a temporary database.

If live-service tests are added later, mark them `@pytest.mark.live` and keep them out of the default CI suite.

## Functional operation

Initialize:

```bash
python main.py init
```

First run each stage explicitly:

```bash
python main.py fetch
python main.py filter
python main.py contacts
python main.py draft
python main.py review
python main.py send --dry-run
```

Only after reviewing the dry run should you send real mail:

```bash
python main.py send
```

Once the stages are trusted, the pipeline can be run together:

```bash
python main.py run
```

## Configuration

Keep behaviour in `config.yaml`: candidate profile, target roles, exclusions, locations, enabled job sources, daily limits and follow-up rules.

Keep secrets in `.env`:

```text
ANTHROPIC_API_KEY=
HUNTER_API_KEY=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@example.com
SMTP_PASSWORD=your_app_password_here
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=you@example.com
IMAP_PASSWORD=your_app_password_here
TRACKING_BASE_URL=
```

For Gmail, use an App Password rather than your normal account password.

## Job sources

The default fetcher uses public RemoteOK and Arbeitnow endpoints. Their responses are normalized into one internal job shape before being written to SQLite. A failure in one source is reported without preventing the other source from running.

Fetching does not call Claude, find contacts or send email.

## Safety model

The intended path is:

`fetch -> filter -> contact -> draft -> human review -> approved -> send`

Sending only processes rows already marked `approved`. `send --dry-run` never connects to SMTP. Start with a small daily limit and review generated messages before increasing it.

Role-based email guessing is low confidence. Prefer verified contacts and manually review addresses before sending.

Open tracking is optional and inherently unreliable. Reply collection through IMAP works independently.

## Database isolation

Production defaults to `data/pipeline.db`.

Tests can set:

```text
JOB_ENGINE_DB_PATH=/temporary/path/pipeline.db
```

This keeps tests away from production data and also makes CLI tests deterministic.
