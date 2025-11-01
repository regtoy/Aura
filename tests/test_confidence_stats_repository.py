import pytest
from unittest.mock import AsyncMock

from app.services.confidence import ConfidenceStats, ConfidenceStatsRepository


class DummyAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyPool:
    def __init__(self, connection):
        self.connection = connection

    def acquire(self):
        return DummyAcquire(self.connection)


@pytest.mark.asyncio
async def test_ensure_schema_executes_create_table():
    connection = AsyncMock()
    pool = DummyPool(connection)
    repo = ConfidenceStatsRepository(pool)

    await repo.ensure_schema()

    connection.execute.assert_awaited()
    create_stmt = connection.execute.await_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS confidence_stats" in create_stmt


@pytest.mark.asyncio
async def test_get_threshold_inserts_default():
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=None)
    pool = DummyPool(connection)
    repo = ConfidenceStatsRepository(pool, default_threshold=0.7, min_threshold=0.2, max_threshold=0.9)

    threshold = await repo.get_threshold("retrieval")

    assert threshold == pytest.approx(0.7)
    connection.execute.assert_awaited()
    upsert_stmt = connection.execute.await_args[0][0]
    assert "INSERT INTO confidence_stats" in upsert_stmt


@pytest.mark.asyncio
async def test_record_outcome_updates_stats():
    row = {
        "metric": "retrieval",
        "sample_count": 10,
        "success_count": 7,
        "failure_count": 3,
        "rolling_score": 0.65,
        "rolling_threshold": 0.6,
    }
    connection = AsyncMock()
    connection.fetchrow = AsyncMock(return_value=row)
    pool = DummyPool(connection)
    repo = ConfidenceStatsRepository(pool, smoothing_factor=0.3)

    updated = await repo.record_outcome("retrieval", score=0.8, passed=True)

    assert isinstance(updated, ConfidenceStats)
    assert updated.sample_count == 11
    assert updated.success_count == 8
    assert updated.failure_count == 3
    assert 0.65 < updated.rolling_score <= 0.8
    assert updated.rolling_threshold <= 0.95

    connection.execute.assert_awaited()
    args = connection.execute.await_args[0][1:]
    assert args[0] == "retrieval"
