"""Command-line entry point for the job hunting engine."""

import argparse
from pathlib import Path

import yaml
from dotenv import load_dotenv

import db
import fetch_jobs
import find_companies
import find_contact
import personalize
import review
import send_email
import follow_up
import tracker
import classify_replies

ROOT = Path(__file__).resolve().parent


def load_config(path="config.yaml"):
    """Load a user config relative to the repository, never the current cwd."""
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    if not config_path.exists():
        raise SystemExit(f"Missing {config_path}. Copy config.example.yaml to config.yaml and edit it.")
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_pipeline(config, auto_approve=False, dry_run=False):
    """Run the functional pipeline. Tests should call individual stages with mocks."""
    db.init_db()
    fetch_jobs.run(config)
    find_companies.run(config)
    find_contact.run(config)
    personalize.run(config)
    review.run(config, auto_approve=auto_approve)
    send_email.run(config, dry_run=dry_run)


def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Simple job hunting outreach engine")
    parser.add_argument("command", choices=[
        "init", "fetch", "filter", "contacts", "draft", "review", "send",
        "follow-up", "check-replies", "classify-replies", "run", "track-server",
    ])
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--auto-approve", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "init":
        db.init_db()
    elif args.command == "fetch":
        db.init_db(); fetch_jobs.run(config)
    elif args.command == "filter":
        db.init_db(); find_companies.run(config)
    elif args.command == "contacts":
        db.init_db(); find_contact.run(config)
    elif args.command == "draft":
        db.init_db(); personalize.run(config)
    elif args.command == "review":
        db.init_db(); review.run(config, auto_approve=args.auto_approve)
    elif args.command == "send":
        db.init_db(); send_email.run(config, dry_run=args.dry_run)
    elif args.command == "follow-up":
        db.init_db(); follow_up.run(config)
    elif args.command == "check-replies":
        db.init_db(); tracker.check_replies()
    elif args.command == "classify-replies":
        db.init_db(); classify_replies.run(config)
    elif args.command == "track-server":
        tracker.serve()
    elif args.command == "run":
        run_pipeline(config, auto_approve=args.auto_approve, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
