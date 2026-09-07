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
├── config.example.yaml     # safe configuration template
├── .env.example            # safe secrets template
├── tests/
│   ├── unit/               # fast, isolated tests; no network
│   ├── integration/        # multiple modules, still offline
│   └── functional/         # CLI smoke tests with isolated DB
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

The tests must never depend on live job APIs, Claude, Hunter, SMTP or IMAP.

### Unit tests

Test pure rules and small components:

```bash
pytest tests/unit
```

These cover normalization, deduplication, filtering and SQLite behaviour. HTTP responses are mocked.

### Integration tests

Exercise several application modules together, but with fake API payloads:

```bash
pytest tests/integration
```

### Functional CLI tests

Exercise the real CLI process while forcing the database into a temporary location:

```bash
pytest tests/functional
```

### Everything used by CI

```bash
pytest -m "not live"
```

Live tests, if added later, should be explicitly marked with `@pytest.mark.live` and never be required for a normal pull request.

## Functional operation

Initialize:

```bash
python main.py init
```

Then run stages explicitly during the first setup:

```bash
python main.py fetch
python main.py filter
python main.py contacts
python main.py draft
python main.py review
python main.py send --dry-run
```

Only after reviewing the dry-run should you send real mail:

```bash
python main.py send
```

The all-in-one command is available once the individual stages are trusted:

```bash
python main.py run
```

## Job sources

The default fetcher uses public RemoteOK and Arbeitnow endpoints. Their responses are normalized into the internal job shape before being written to SQLite. A failure in one source is reported without preventing the other source from running.

Fetching does **not** call Claude, find contacts or send email. This separation makes the fetcher easy to test and safe to run repeatedly.

## Configuration

Keep behaviour in `config.yaml`:

- candidate profile
- target job titles
- excluded seniority terms
- remote/location rules
- enabled job sources
- daily email limit
- follow-up timing
- Claude model

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

## Safety model

The intended path is:

`fetch -> filter -> contact -> draft -> human review -> approved -> send`

Sending only processes rows already marked `approved`. `send --dry-run` never connects to SMTP. Start with a small daily limit and review generated messages before increasing it.

Role-based email guessing is low confidence. Prefer verified contacts and manually review addresses before sending.

Open tracking is optional and inherently unreliable. Reply collection through IMAP works independently.

## Database isolation for tests

Production defaults to:

```text
data/pipeline.db
```

Tests can set:

```text
JOB_ENGINE_DB_PATH=/temporary/path/pipeline.db
```

This prevents test runs from modifying production data and also makes CLI tests deterministic.
