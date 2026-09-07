import find_companies


def test_title_matches_accepts_configured_role():
    assert find_companies.title_matches(
        "Junior Software Developer",
        ["junior developer"],
        ["senior", "lead"],
    )


def test_title_matches_rejects_senior_roles():
    assert not find_companies.title_matches(
        "Senior Software Developer",
        ["junior developer"],
        ["senior", "lead"],
    )


def test_region_matches_remote_when_remote_only():
    assert find_companies.region_matches("Remote - Ireland", ["Ireland"], remote_only=True)
    assert not find_companies.region_matches("London, UK", ["United Kingdom"], remote_only=True)


def test_region_matches_accepts_configured_non_remote_region():
    assert find_companies.region_matches("Dublin, Ireland", ["Ireland"], remote_only=False)
    assert not find_companies.region_matches("Berlin, Germany", ["Ireland"], remote_only=False)


def test_filter_run_updates_database(test_db, base_config):
    conn = __import__("db").get_connection()
    __import__("db").add_company(
        conn,
        "Good Co",
        "good.example",
        "test",
        "Junior Developer",
        "https://good.example/job/1",
        "This is a sufficiently detailed job description for the test.",
        "Remote - Ireland",
        "python",
    )
    __import__("db").add_company(
        conn,
        "Bad Co",
        "bad.example",
        "test",
        "Senior Developer",
        "https://bad.example/job/1",
        "This is a sufficiently detailed job description for the test.",
        "Remote - Ireland",
        "python",
    )
    conn.close()

    find_companies.run(base_config)

    conn = __import__("db").get_connection()
    rows = conn.execute("SELECT name, status FROM companies ORDER BY name").fetchall()
    conn.close()

    assert [(r["name"], r["status"]) for r in rows] == [
        ("Bad Co", "filtered_out"),
        ("Good Co", "filtered_in"),
    ]
