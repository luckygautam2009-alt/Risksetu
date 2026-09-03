from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.main import app

# Add a dedicated test router for validating error contracts
_test_router = APIRouter(prefix="/api/v1/test-errors")


@_test_router.get("/unhandled")
def raise_unhandled() -> None:
    raise RuntimeError("Sensitive DB path: /var/secrets/db_password.txt crashed with syntax error")


@_test_router.get("/not-found")
def raise_not_found() -> None:
    raise NotFoundError("Region not found", details=[{"field": "region_id"}])


@_test_router.get("/conflict")
def raise_conflict() -> None:
    raise ConflictError("User already exists")


@_test_router.get("/forbidden")
def raise_forbidden() -> None:
    raise ForbiddenError("Insufficient administrative privileges")


@_test_router.get("/unauthorized")
def raise_unauthorized() -> None:
    raise UnauthorizedError("Invalid or expired session token")


@_test_router.get("/validation")
def raise_validation() -> None:
    raise ValidationAppError("Field 'latitude' must be between -90 and 90")


@_test_router.get("/pydantic-validation")
def pydantic_validation_endpoint(count: int) -> dict[str, int]:
    return {"count": count}


app.include_router(_test_router)



def test_standard_error_envelope_structure(client: TestClient) -> None:
    """Error responses must strictly follow the standard error contract."""
    response = client.get("/api/v1/nonexistent-endpoint")
    assert response.status_code == 404
    body = response.json()

    assert "error" in body
    err = body["error"]
    assert err["code"] == "NOT_FOUND"
    assert isinstance(err["message"], str)
    assert isinstance(err["details"], list)
    assert "request_id" in err


def test_http_method_not_allowed_mapping(client: TestClient) -> None:
    """405 status codes must map to METHOD_NOT_ALLOWED machine code."""
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    body = response.json()
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_domain_app_errors_preserve_contract(client: TestClient) -> None:
    """Domain error classes return appropriate HTTP status codes and machine codes."""
    cases = [
        ("/api/v1/test-errors/not-found", 404, "NOT_FOUND"),
        ("/api/v1/test-errors/conflict", 409, "CONFLICT"),
        ("/api/v1/test-errors/forbidden", 403, "FORBIDDEN"),
        ("/api/v1/test-errors/unauthorized", 401, "UNAUTHORIZED"),
        ("/api/v1/test-errors/validation", 422, "VALIDATION_ERROR"),
    ]
    for path, expected_status, expected_code in cases:
        resp = client.get(path)
        assert resp.status_code == expected_status
        body = resp.json()
        assert body["error"]["code"] == expected_code
        assert "request_id" in body["error"]


def test_unexpected_exception_masks_internal_details() -> None:
    """Unhandled exceptions return 500 INTERNAL_ERROR with zero leaked stack or secrets."""
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.get("/api/v1/test-errors/unhandled")
    assert response.status_code == 500
    body = response.json()

    assert "error" in body
    err = body["error"]
    assert err["code"] == "INTERNAL_ERROR"
    assert err["message"] == "An unexpected error occurred. Please try again."
    assert err["details"] == []
    assert "request_id" in err

    # CRITICAL: Verify sensitive strings from the exception are NOT leaked in response
    response_text = response.text
    assert "Sensitive DB path" not in response_text
    assert "/var/secrets" not in response_text
    assert "RuntimeError" not in response_text


def test_fastapi_request_validation_error_envelope(client: TestClient) -> None:
    """Pydantic query/body validation failures return 422 with standard envelope."""
    response = client.get("/api/v1/test-errors/pydantic-validation?count=invalid_int")
    assert response.status_code == 422
    body = response.json()
    assert "error" in body
    err = body["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["message"] == "Request validation failed."
    assert isinstance(err["details"], list)
    assert len(err["details"]) > 0
    assert "request_id" in err


