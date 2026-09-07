"""Command-line entry point for the job hunting engine."""

import argparse
import os
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
    config_path = ROOT / path
    if not config_path.exists():
        raise SystemExit(
            f"Missing {config_path}. Copy config.example.yaml to config.yaml and edit it."
        )
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def run_pipeline(config):
    db.init_db()
    fetch_jobs.run(config)
    find_companies.run(config)
    find_contact.run(config)
    personalize.run(config)
    review.run(config)
    send_email.run(config)


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
        if args.auto_approve:
            config.setdefault("outreach", {})["auto_approve"] = True
        run_pipeline(config)


if __name__ == "__main__":
    main()
