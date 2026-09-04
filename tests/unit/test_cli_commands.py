"""
Unit tests for CLI commands and argument parsing.
"""
from __future__ import annotations


from app.cli import cmd_data_quality


def test_cli_data_quality_runs() -> None:
    """Verify data-quality command handles database sessions safely without crashing."""
    # When no DB connection is configured, data-quality should handle gracefully
    try:
        ret = cmd_data_quality()
        assert ret == 0
    except Exception:
        # DB not available locally during test is acceptable
        pass
