import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session", autouse=True)
def run_database_migrations():
    """Ensure database schema is up-to-date before running tests."""
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app)
