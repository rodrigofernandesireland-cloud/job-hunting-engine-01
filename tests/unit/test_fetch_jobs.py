import fetch_jobs


def test_normalize_jobs_cleans_fields_and_fills_domain():
    jobs = fetch_jobs.normalize_jobs([{
        "source": "test", "external_id": "1",
        "title": "  Junior Python Developer  ", "company_name": "  Example Ltd  ",
        "company_domain": None, "location": " Remote - Ireland ",
        "url": "https://example.com/jobs/1",
        "description": "  Build useful Python services for customers.  ",
        "tags": "python, django",
    }])
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Junior Python Developer"
    assert jobs[0]["company_name"] == "Example Ltd"
    assert jobs[0]["company_domain"] == "example.com"
    assert jobs[0]["location"] == "Remote - Ireland"
    assert jobs[0]["tags"] == ["python", "django"]


def test_normalize_jobs_drops_incomplete_jobs():
    jobs = fetch_jobs.normalize_jobs([
        {"source": "test", "title": "Developer", "url": "https://x.test", "description": ""},
        {"source": "test", "title": "", "url": "https://x.test", "description": "valid description"},
    ])
    assert jobs == []


def test_normalize_jobs_deduplicates_same_source_and_external_id():
    job = {
        "source": "remoteok", "external_id": "123", "title": "Junior Developer",
        "company_name": "Example", "url": "https://example.com/job/123",
        "description": "A sufficiently long job description for testing.",
    }
    assert len(fetch_jobs.normalize_jobs([job, dict(job)])) == 1


def test_fetch_remoteok_maps_public_payload(monkeypatch):
    monkeypatch.setattr(fetch_jobs, "_request_json", lambda url: [
        {"legal": "metadata"},
        {"id": 123, "position": "Junior Developer", "company": "Example",
         "company_url": "https://example.com", "location": "Remote - Ireland",
         "url": "https://remoteok.com/remote-jobs/123",
         "description": "Build and maintain software for customers.", "tags": ["python"]},
    ])
    jobs = fetch_jobs.fetch_remoteok()
    assert len(jobs) == 1
    assert jobs[0]["external_id"] == "123"
    assert jobs[0]["company_domain"] == "example.com"


def test_fetch_arbeitnow_maps_public_payload(monkeypatch):
    monkeypatch.setattr(fetch_jobs, "_request_json", lambda url: {"data": [{
        "slug": "junior-python-example", "title": "Junior Python Developer",
        "company_name": "Example", "company_url": "https://example.org",
        "location": "Remote - Ireland", "url": "https://example.org/jobs/1",
        "description": "Build and maintain Python services for customers.",
        "tags": ["python"], "created_at": "2026-09-01",
    }]})
    jobs = fetch_jobs.fetch_arbeitnow()
    assert len(jobs) == 1
    assert jobs[0]["external_id"] == "junior-python-example"
    assert jobs[0]["company_domain"] == "example.org"


def test_run_continues_when_one_source_fails(test_db, monkeypatch, base_config):
    monkeypatch.setattr(fetch_jobs, "fetch_remoteok", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(fetch_jobs, "fetch_arbeitnow", lambda: [{
        "source": "arbeitnow", "external_id": "1", "title": "Junior Developer",
        "company_name": "Example", "company_domain": "example.org",
        "location": "Remote - Ireland", "url": "https://example.org/jobs/1",
        "description": "A sufficiently long description for testing.", "tags": [],
    }])
    assert fetch_jobs.run(base_config) == 1
