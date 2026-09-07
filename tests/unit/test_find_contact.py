import find_contact


def test_pattern_guess_role_email_has_source():
    contact = find_contact.pattern_guess_role_email("example.com")

    assert contact["email"] == "careers@example.com"
    assert contact["confidence"] == "guessed_low"
    assert contact["source"] == "pattern_fallback"


def test_hunter_domain_search_marks_hunter_source(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": {
                    "emails": [
                        {
                            "first_name": "Ana",
                            "last_name": "Silva",
                            "position": "Talent Acquisition Manager",
                            "value": "ana@example.com",
                            "verification": {"status": "valid"},
                        }
                    ]
                }
            }

    monkeypatch.setattr(find_contact.requests, "get", lambda *args, **kwargs: FakeResponse())

    contact = find_contact.hunter_domain_search(
        "example.com", "test-key", ["talent acquisition"]
    )

    assert contact["name"] == "Ana Silva"
    assert contact["email"] == "ana@example.com"
    assert contact["confidence"] == "verified"
    assert contact["source"] == "hunter"
