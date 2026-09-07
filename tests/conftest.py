import pytest

import db


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "pipeline.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    yield db_path


@pytest.fixture
def base_config():
    return {
        "candidate": {
            "name": "Test Candidate",
            "email": "test@example.com",
            "location": "Dublin, Ireland",
            "linkedin_url": "https://example.com/linkedin",
            "portfolio_url": "https://example.com",
            "pitch": "Junior developer testing profile.",
        },
        "search": {
            "job_titles": ["junior developer", "graduate developer"],
            "exclude_keywords": ["senior", "lead", "principal"],
            "remote_only": True,
            "target_regions": ["Ireland", "United Kingdom", "Remote Europe"],
            "sources": {"remoteok": True, "arbeitnow": True},
        },
        "outreach": {
            "daily_send_limit": 10,
            "follow_up_after_days": 5,
            "max_follow_ups": 1,
            "send_window_hours": [0, 24],
            "subject_line": "Junior Developer — {candidate_name}, based in {candidate_location}",
            "signoff": "Best,\n{candidate_name}\n{candidate_linkedin}",
        },
        "contact_finding": {"preferred_titles": ["recruiter", "hiring manager"]},
        "claude": {"model": "test-model", "personalization_temperature": 0},
    }
