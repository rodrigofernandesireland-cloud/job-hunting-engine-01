# Job Hunting Engine

A small, local-first job-search assistant. It finds suitable jobs, filters them, finds a contact, drafts a personalized email, lets you review it, and only then sends it.

## The idea

Think of the project as a pipeline:

`jobs -> filter -> contact -> draft -> review -> send -> replies`

SQLite stores the state so you can stop and restart without losing progress. Claude is used only for writing outreach and classifying replies. Email is sent/read through your mailbox.

## What is intentionally automatic

- Fetch job listings from the configured sources.
- Remove jobs that do not match your basic criteria.
- Find a contact when Hunter is configured; otherwise use a role inbox such as `careers@domain`.
- Draft short personalized emails.
- Review drafts before sending.
- Send approved emails with a daily limit.
- Check replies and optionally classify them with Claude.

## What is intentionally manual

- Your profile and search criteria.
- Final approval before sending.
- Handling interested/ambiguous replies.
- Choosing whether open tracking is worth using.

Do not enable automatic sending until you have tested the full flow with `--dry-run`.

## Setup

Requires Python 3.11+.

```bash
git clone https://github.com/rodrigofernandesireland-cloud/job-hunting-engine-01.git
cd job-hunting-engine-01
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
cp config.example.yaml config.yaml
```

Edit `config.yaml` with your real profile. Put your CV at the path configured by `candidate.cv_path` if you plan to use it.

## Secrets

`.env` is for secrets and mailbox/API credentials. It must not be committed.

Minimum for drafting:

```text
ANTHROPIC_API_KEY=your_key
```

For Gmail sending/reading:

```text
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_google_app_password
IMAP_HOST=imap.gmail.com
IMAP_PORT=993
IMAP_USER=you@gmail.com
IMAP_PASSWORD=your_google_app_password
```

Use a Gmail App Password, not your normal Google password. Hunter and Adzuna are optional.

## First test

Initialize the database:

```bash
python main.py init
```

Run each stage manually while testing:

```bash
python main.py fetch
python main.py filter
python main.py contacts
python main.py draft
python main.py review
python main.py send --dry-run
```

Only after the dry run looks correct should you send:

```bash
python main.py send
```

You can also run the basic pipeline in one command:

```bash
python main.py run
```

For a fully unattended run, use `--auto-approve` only if you accept the risk of sending AI-generated messages without a human review step.

## Replies and follow-ups

Check the mailbox:

```bash
python main.py check-replies
python main.py classify-replies
python main.py follow-up
```

Follow-ups are drafted, not immediately sent. Review them with `python main.py review`.

## Open tracking

Open tracking requires the tracking server to be reachable by the recipient's email client. `localhost` will not work for external recipients.

Start it locally with:

```bash
python main.py track-server
```

Then set `TRACKING_BASE_URL` to a public HTTPS address if you deploy the server. If you do not need open tracking, leave the server disabled; reply tracking works independently through IMAP.

## Important implementation notes

- The repository currently uses SQLite and local files; there is no web UI or background scheduler.
- The code uses package-style relative imports in several modules, so the CLI should be the normal entry point rather than executing those modules directly.
- `schema.sql` is the canonical schema. Keep it beside the Python files unless you deliberately change the database path.
- Role-based email guessing is low confidence. Prefer verified contacts and review addresses before sending.
- Email open tracking is inherently unreliable because many mail clients proxy or block tracking images.

## Recommended operating model

Start with 5–10 approved emails/day. Review every generated message. Increase volume only after you have validated the job filters, contact quality, email wording, and unsubscribe handling.
