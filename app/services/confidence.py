from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import asyncpg


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

    _UPSERT_SQL = """
    INSERT INTO confidence_stats (metric, sample_count, success_count, failure_count, rolling_score, rolling_threshold, updated_at)
    VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
    ON CONFLICT (metric) DO UPDATE
    SET sample_count = EXCLUDED.sample_count,
        success_count = EXCLUDED.success_count,
        failure_count = EXCLUDED.failure_count,
        rolling_score = EXCLUDED.rolling_score,
        rolling_threshold = EXCLUDED.rolling_threshold,
        updated_at = CURRENT_TIMESTAMP
    """

    _SELECT_SQL = """
    SELECT metric, sample_count, success_count, failure_count, rolling_score, rolling_threshold
    FROM confidence_stats
    WHERE metric = $1
    """

    _CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS confidence_stats (
        metric TEXT PRIMARY KEY,
        sample_count INTEGER NOT NULL DEFAULT 0,
        success_count INTEGER NOT NULL DEFAULT 0,
        failure_count INTEGER NOT NULL DEFAULT 0,
        rolling_score DOUBLE PRECISION NOT NULL,
        rolling_threshold DOUBLE PRECISION NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """

    def __init__(
        self,
        pool: asyncpg.Pool,
        *,
        default_threshold: float = 0.6,
        smoothing_factor: float = 0.2,
        min_threshold: float = 0.2,
        max_threshold: float = 0.95,
    ) -> None:
        if not 0.0 < smoothing_factor <= 1.0:
            raise ValueError("smoothing_factor must be in the (0, 1] range")
        if not 0.0 <= min_threshold <= max_threshold <= 1.0:
            raise ValueError("threshold bounds must satisfy 0 <= min <= max <= 1")

        self._pool = pool
        self._smoothing_factor = smoothing_factor
        self._min_threshold = min_threshold
        self._max_threshold = max_threshold
        self._default_threshold = max(min_threshold, min(max_threshold, default_threshold))

    async def ensure_schema(self) -> None:
        async with self._pool.acquire() as connection:
            await connection.execute(self._CREATE_TABLE_SQL)

    async def ensure_metric(self, metric: str) -> ConfidenceStats:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._SELECT_SQL, metric)
            if row is None:
                stats = ConfidenceStats.with_default(metric, self._default_threshold)
                await connection.execute(self._UPSERT_SQL, *stats.as_tuple())
                return stats
            return self._row_to_stats(row)

    async def get_threshold(self, metric: str) -> float:
        stats = await self.ensure_metric(metric)
        return stats.rolling_threshold

    async def record_outcome(self, metric: str, *, score: float, passed: bool) -> ConfidenceStats:
        async with self._pool.acquire() as connection:
            row = await connection.fetchrow(self._SELECT_SQL, metric)
            if row is None:
                stats = ConfidenceStats.with_default(metric, self._default_threshold)
            else:
                stats = self._row_to_stats(row)

            updated = stats.updated(
                score=score,
                passed=passed,
                smoothing_factor=self._smoothing_factor,
                min_threshold=self._min_threshold,
                max_threshold=self._max_threshold,
            )
            await connection.execute(self._UPSERT_SQL, *updated.as_tuple())
            return updated

    @staticmethod
    def _row_to_stats(row: Any) -> ConfidenceStats:
        return ConfidenceStats(
            metric=str(row["metric"]),
            sample_count=int(row["sample_count"]),
            success_count=int(row["success_count"]),
            failure_count=int(row["failure_count"]),
            rolling_score=float(row["rolling_score"]),
            rolling_threshold=float(row["rolling_threshold"]),
        )
