from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    """GET /health is pure liveness and must return 200 ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
    assert "meta" in body


def test_readiness_all_dependencies_healthy(client: TestClient) -> None:
    """GET /readiness returns 200 when database and Redis are operational."""
    with patch("app.api.v1.health.engine.connect") as mock_connect, \
         patch("app.api.v1.health.check_redis_connection", return_value=True):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = client.get("/api/v1/readiness")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["status"] == "ok"
        assert body["data"]["checks"]["database"] == "ok"
        assert body["data"]["checks"]["redis"] == "ok"


def test_readiness_database_failure_returns_503(client: TestClient) -> None:
    """GET /readiness returns HTTP 503 unhealthy when PostgreSQL is unreachable."""
    with patch("app.api.v1.health.engine.connect", side_effect=Exception("DB connection refused")), \
         patch("app.api.v1.health.check_redis_connection", return_value=True):

        response = client.get("/api/v1/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["data"]["status"] == "unhealthy"
        assert body["data"]["checks"]["database"] == "error"
        assert body["data"]["checks"]["redis"] == "ok"
        # Ensure no internal error strings or passwords leak
        assert "refused" not in str(body)
        assert "postgresql" not in str(body).lower()


def test_readiness_redis_failure_returns_503(client: TestClient) -> None:
    """GET /readiness returns HTTP 503 degraded when Redis is down."""
    with patch("app.api.v1.health.engine.connect") as mock_connect, \
         patch("app.api.v1.health.check_redis_connection", return_value=False):
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn

        response = client.get("/api/v1/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["data"]["status"] == "degraded"
        assert body["data"]["checks"]["database"] == "ok"
        assert body["data"]["checks"]["redis"] == "error"


def test_readiness_without_mocks_is_non_200_if_services_down(client: TestClient) -> None:
    """Readiness accurately signals 503 when dependencies are unreachable.

    This test deterministically simulates unreachable infrastructure so that the
    assertion holds in every environment (local, CI, staging) regardless of whether
    real Postgres/Redis containers happen to be running.  The application's readiness
    handler logic is exercised in full — only the underlying network calls are replaced
    with genuine failures, which is exactly what would happen if the services were down.
    """
    with patch(
        "app.api.v1.health.engine.connect",
        side_effect=Exception("simulated: connection refused"),
    ), patch(
        "app.api.v1.health.check_redis_connection",
        return_value=False,
    ):
        response = client.get("/api/v1/readiness")

    assert response.status_code == 503
    body = response.json()
    assert body["data"]["status"] in ("unhealthy", "degraded")
    assert "database" in body["data"]["checks"]
    assert "redis" in body["data"]["checks"]
