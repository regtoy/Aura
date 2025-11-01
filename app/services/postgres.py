from __future__ import annotations

import asyncio
from dataclasses import dataclass

import asyncpg


@dataclass(slots=True)
class PostgresConnectionTester:
    """Utility providing explicit connection testing to PostgreSQL."""

    dsn: str
    _pool: asyncpg.Pool | None = None

    async def _ensure_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=1)
        return self._pool

    async def test_connection(self) -> bool:
        pool = await self._ensure_pool()
        async with pool.acquire() as connection:
            await connection.execute("SELECT 1")
        return True

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    def test_connection_sync(self, timeout: float = 5.0) -> bool:
        """Blocking helper that can be used from synchronous contexts."""

        return asyncio.run(asyncio.wait_for(self.test_connection(), timeout=timeout))
