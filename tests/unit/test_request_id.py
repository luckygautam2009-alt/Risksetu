import re

from fastapi.testclient import TestClient

UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def test_request_id_generated_when_missing(client: TestClient) -> None:
    """When no X-Request-ID header is provided, the server generates a valid UUIDv4."""
    response = client.get("/api/v1/health")
    assert "X-Request-ID" in response.headers
    req_id = response.headers["X-Request-ID"]
    assert UUID_REGEX.match(req_id)


def test_valid_custom_request_id_is_accepted(client: TestClient) -> None:
    """A safe client-supplied X-Request-ID is preserved and propagated."""
    custom_id = "req_12345-prod_alpha"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id


def test_invalid_chars_request_id_is_rejected_and_regenerated(client: TestClient) -> None:
    """An X-Request-ID with invalid characters is rejected and replaced with a safe UUIDv4."""
    malicious_ids = [
        "req<script>alert(1)</script>",
        "req\r\nInjected-Header: evil",
        "req with spaces 123",
        "req; DROP TABLE users;--",
        "req$#!%^&*()",
    ]
    for bad_id in malicious_ids:
        response = client.get("/api/v1/health", headers={"X-Request-ID": bad_id})
        reflected = response.headers["X-Request-ID"]
        assert reflected != bad_id
        assert UUID_REGEX.match(reflected)


def test_excessively_long_request_id_is_rejected(client: TestClient) -> None:
    """An X-Request-ID exceeding 64 characters is rejected and replaced with a safe UUIDv4."""
    too_long = "a" * 65
    response = client.get("/api/v1/health", headers={"X-Request-ID": too_long})
    reflected = response.headers["X-Request-ID"]
    assert reflected != too_long
    assert UUID_REGEX.match(reflected)


def test_request_id_included_in_error_response(client: TestClient) -> None:
    """Error envelopes must always contain the matching request ID."""
    custom_id = "req-test-error-404"
    response = client.get("/api/v1/nonexistent", headers={"X-Request-ID": custom_id})
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["request_id"] == custom_id
