from unittest.mock import MagicMock, patch

import redis

from app.core.redis import check_redis_connection, get_redis_client, get_redis_pool


def test_redis_connection_pool_initialized() -> None:
    """Connection pool is cached and configured."""
    pool = get_redis_pool()
    assert isinstance(pool, redis.ConnectionPool)
    client = get_redis_client()
    assert isinstance(client, redis.Redis)


def test_check_redis_connection_healthy() -> None:
    """Returns True when Redis ping succeeds."""
    with patch("redis.Redis.from_url") as mock_from_url:
        mock_instance = MagicMock()
        mock_instance.ping.return_value = True
        mock_from_url.return_value = mock_instance

        assert check_redis_connection() is True


def test_check_redis_connection_failure_handled_gracefully() -> None:
    """Returns False when Redis connection fails, without raising or leaking credentials."""
    for error_type in [
        redis.ConnectionError("Connection refused to redis:6379"),
        redis.TimeoutError("Connection timed out"),
        redis.RedisError("General Redis fault"),
        OSError("Network unreachable"),
    ]:
        with patch("redis.Redis.from_url", side_effect=error_type):
            result = check_redis_connection(timeout_seconds=0.1)
            assert result is False
