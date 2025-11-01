from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from apps.api.services.confidence import ConfidenceStats, ConfidenceStatsRepository
from packages.db.models import ConfidenceStatsTable


@pytest_asyncio.fixture
async def engine() -> AsyncEngine:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(engine: AsyncEngine) -> async_sessionmaker:
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_ensure_schema_executes_create_table(engine: AsyncEngine):
    factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = ConfidenceStatsRepository(factory, engine=engine)

    await repo.ensure_schema()

    async with engine.begin() as conn:
        tables = await conn.run_sync(lambda sync_conn: set(sa_inspect(sync_conn).get_table_names()))

    assert "confidence_stats" in tables


@pytest.mark.asyncio
async def test_get_threshold_inserts_default(
    session_factory: async_sessionmaker, engine: AsyncEngine
):
    repo = ConfidenceStatsRepository(
        session_factory,
        engine=engine,
        default_threshold=0.7,
        min_threshold=0.2,
        max_threshold=0.9,
    )

    threshold = await repo.get_threshold("retrieval")

    assert threshold == pytest.approx(0.7)

    async with session_factory() as session:
        row = await session.get(ConfidenceStatsTable, "retrieval")
    assert row is not None
    assert row.rolling_threshold == pytest.approx(0.7)


@pytest.mark.asyncio
async def test_record_outcome_updates_stats(
    session_factory: async_sessionmaker, engine: AsyncEngine
):
    repo = ConfidenceStatsRepository(session_factory, engine=engine, smoothing_factor=0.3)

    initial = await repo.ensure_metric("retrieval")
    assert isinstance(initial, ConfidenceStats)

    updated = await repo.record_outcome("retrieval", score=0.8, passed=True)

    assert isinstance(updated, ConfidenceStats)
    assert updated.sample_count == initial.sample_count + 1
    assert updated.success_count == initial.success_count + 1
    assert updated.failure_count == initial.failure_count
    assert updated.rolling_score >= initial.rolling_score
    assert updated.rolling_threshold <= 0.95

    async with session_factory() as session:
        row = await session.get(ConfidenceStatsTable, "retrieval")
    assert row is not None
    assert row.success_count == updated.success_count
