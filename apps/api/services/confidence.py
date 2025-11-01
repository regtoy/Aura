from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlmodel import SQLModel, select

from packages.db.models import ConfidenceStatsTable


@dataclass(slots=True)
class ConfidenceStats:
    """Represents aggregated confidence statistics for a given metric."""

    metric: str
    sample_count: int
    success_count: int
    failure_count: int
    rolling_score: float
    rolling_threshold: float

    @property
    def success_rate(self) -> float:
        total = self.sample_count
        return (self.success_count / total) if total else 0.0

    @property
    def failure_rate(self) -> float:
        total = self.sample_count
        return (self.failure_count / total) if total else 0.0

    @classmethod
    def with_default(cls, metric: str, threshold: float) -> "ConfidenceStats":
        return cls(
            metric=metric,
            sample_count=0,
            success_count=0,
            failure_count=0,
            rolling_score=threshold,
            rolling_threshold=threshold,
        )

    def as_tuple(self) -> tuple[Any, ...]:
        return (
            self.metric,
            self.sample_count,
            self.success_count,
            self.failure_count,
            self.rolling_score,
            self.rolling_threshold,
        )

    def updated(
        self,
        *,
        score: float,
        passed: bool,
        smoothing_factor: float,
        min_threshold: float,
        max_threshold: float,
    ) -> "ConfidenceStats":
        success_count = self.success_count + (1 if passed else 0)
        failure_count = self.failure_count + (0 if passed else 1)
        sample_count = success_count + failure_count

        if self.sample_count == 0:
            rolling_score = score
        else:
            rolling_score = self.rolling_score + smoothing_factor * (score - self.rolling_score)

        success_rate = success_count / sample_count if sample_count else 0.0
        dynamic_bias = (success_rate - 0.5) * 0.2
        base_threshold = rolling_score + dynamic_bias
        rolling_threshold = max(min_threshold, min(max_threshold, base_threshold))

        return ConfidenceStats(
            metric=self.metric,
            sample_count=sample_count,
            success_count=success_count,
            failure_count=failure_count,
            rolling_score=rolling_score,
            rolling_threshold=rolling_threshold,
        )


class ConfidenceStatsRepository:
    """Repository responsible for the `confidence_stats` table management."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        engine: AsyncEngine | None = None,
        default_threshold: float = 0.6,
        smoothing_factor: float = 0.2,
        min_threshold: float = 0.2,
        max_threshold: float = 0.95,
    ) -> None:
        if not 0.0 < smoothing_factor <= 1.0:
            raise ValueError("smoothing_factor must be in the (0, 1] range")
        if not 0.0 <= min_threshold <= max_threshold <= 1.0:
            raise ValueError("threshold bounds must satisfy 0 <= min <= max <= 1")

        self._session_factory = session_factory
        self._engine: AsyncEngine | None = engine
        self._smoothing_factor = smoothing_factor
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        self._default_threshold = max(min_threshold, min(max_threshold, default_threshold))

    async def ensure_schema(self) -> None:
        if self._engine is None:
            raise RuntimeError("Session factory is not bound to an async engine")
        async with self._engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    async def ensure_metric(self, metric: str) -> ConfidenceStats:
        async with self._session_factory() as session:
            row = await session.get(ConfidenceStatsTable, metric)
            if row is None:
                stats = ConfidenceStats.with_default(metric, self._default_threshold)
                row = ConfidenceStatsTable(
                    metric=stats.metric,
                    sample_count=stats.sample_count,
                    success_count=stats.success_count,
                    failure_count=stats.failure_count,
                    rolling_score=stats.rolling_score,
                    rolling_threshold=stats.rolling_threshold,
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(row)
                await session.commit()
                await session.refresh(row)
                return stats
            return self._table_to_stats(row)

    async def get_threshold(self, metric: str) -> float:
        stats = await self.ensure_metric(metric)
        return stats.rolling_threshold

    async def record_outcome(self, metric: str, *, score: float, passed: bool) -> ConfidenceStats:
        async with self._session_factory() as session:
            row = await session.get(ConfidenceStatsTable, metric)
            if row is None:
                stats = ConfidenceStats.with_default(metric, self._default_threshold)
            else:
                stats = self._table_to_stats(row)

            updated = stats.updated(
                score=score,
                passed=passed,
                smoothing_factor=self._smoothing_factor,
                min_threshold=self._min_threshold,
                max_threshold=self._max_threshold,
            )

            if row is None:
                row = ConfidenceStatsTable(metric=metric)
                session.add(row)

            row.sample_count = updated.sample_count
            row.success_count = updated.success_count
            row.failure_count = updated.failure_count
            row.rolling_score = updated.rolling_score
            row.rolling_threshold = updated.rolling_threshold
            row.updated_at = datetime.now(timezone.utc)

            await session.commit()
            await session.refresh(row)
            return updated

    @staticmethod
    def _table_to_stats(row: ConfidenceStatsTable) -> ConfidenceStats:
        return ConfidenceStats(
            metric=row.metric,
            sample_count=row.sample_count,
            success_count=row.success_count,
            failure_count=row.failure_count,
            rolling_score=row.rolling_score,
            rolling_threshold=row.rolling_threshold,
        )

