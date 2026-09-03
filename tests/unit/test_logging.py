from app.core.logging import _scrub_sensitive


def test_scrub_sensitive_top_level_keys() -> None:
    """Keys matching passwords, tokens, secrets, or API keys are redacted."""
    event = {
        "event": "user_login",
        "username": "officer_1",
        "password": "SuperSecretPassword123!",
        "token": "eyJhbGciOi...",
        "api_key": "live_key_9999",
        "refresh_token": "rt_8888",
    }
    scrubbed = _scrub_sensitive(None, "info", event)
    assert scrubbed["username"] == "officer_1"
    assert scrubbed["password"] == "***REDACTED***"
    assert scrubbed["token"] == "***REDACTED***"
    assert scrubbed["api_key"] == "***REDACTED***"
    assert scrubbed["refresh_token"] == "***REDACTED***"


def test_scrub_sensitive_nested_structures() -> None:
    """Nested dictionaries and lists are recursively scrubbed."""
    event = {
        "event": "request_data",
        "payload": {
            "auth": {"jwt": "header.payload.sig", "user_id": 42},
            "credentials": [{"type": "secret_key", "secret": "shhh"}],
        },
    }
    scrubbed = _scrub_sensitive(None, "info", event)
    assert scrubbed["payload"]["auth"]["user_id"] == 42
    assert scrubbed["payload"]["auth"]["jwt"] == "***REDACTED***"
    assert scrubbed["payload"]["credentials"][0]["secret"] == "***REDACTED***"


def test_scrub_bearer_header_string() -> None:
    """String values containing raw Bearer tokens are redacted."""
    event = {
        "event": "http_request",
        "authorization_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M",
    }
    scrubbed = _scrub_sensitive(None, "info", event)
    assert scrubbed["authorization_header"] == "***REDACTED***"
