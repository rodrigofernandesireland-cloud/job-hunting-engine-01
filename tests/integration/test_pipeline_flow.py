import db
import fetch_jobs
import find_companies
import pytest


@pytest.mark.integration
def test_offline_fetch_to_filter_flow(test_db, base_config, monkeypatch):
    remoteok_payload = [{
        "id": 100,
        "position": "Junior Developer",
        "company": "Example Ltd",
        "company_url": "https://example.com",
        "location": "Remote - Ireland",
        "url": "https://remoteok.com/remote-jobs/100",
        "description": "Build and maintain software with a small engineering team.",
        "tags": ["python", "remote"],
    }]

    def fake_request(url, params=None):
        if url == fetch_jobs.REMOTEOK_URL:
            return remoteok_payload
        if url == fetch_jobs.ARBEITNOW_URL:
            return {"data": []}
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(fetch_jobs, "_request_json", fake_request)
    assert fetch_jobs.run(base_config) == 1

    find_companies.run(base_config)

    conn = db.get_connection()
    row = conn.execute("SELECT * FROM companies WHERE job_url = ?", (remoteok_payload[0]["url"],)).fetchone()
    conn.close()

    assert row["status"] == "filtered_in"
    assert row["source"] == "remoteok"
