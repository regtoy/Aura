import inspect
from collections.abc import Awaitable
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.postgres import PostgresConnectionTester
from app.services.qdrant import QdrantConnectionTester


@pytest.mark.asyncio
async def test_postgres_connection_tester(monkeypatch):
    connection_mock = AsyncMock()

    class DummyAcquire:
        async def __aenter__(self):
            return connection_mock

        async def __aexit__(self, exc_type, exc, tb):
            return False

    pool_mock = MagicMock()
    pool_mock.acquire.return_value = DummyAcquire()
    pool_mock.close = AsyncMock()

    async def create_pool(**kwargs):
        return pool_mock

    monkeypatch.setattr("app.services.postgres.asyncpg.create_pool", create_pool)

    tester = PostgresConnectionTester("postgresql://test")
    assert await tester.test_connection() is True
    connection_mock.execute.assert_awaited_with("SELECT 1")
    await tester.close()
    pool_mock.close.assert_awaited()


def test_postgres_sync_helper(monkeypatch):
    async def fake_test(self) -> bool:
        return True

    captured: dict[str, object] = {}

    def wait_for_stub(coro: Awaitable, *, timeout: float):
        captured["coro"] = coro
        captured["timeout"] = timeout
        coro.close()
        return "wait-result"

    run_calls: list[object] = []

    def run_stub(arg: object):
        run_calls.append(arg)
        return True

    monkeypatch.setattr(PostgresConnectionTester, "test_connection", fake_test)
    monkeypatch.setattr("app.services.postgres.asyncio.wait_for", wait_for_stub)
    monkeypatch.setattr("app.services.postgres.asyncio.run", run_stub)

    tester = PostgresConnectionTester("postgresql://test")

    result = tester.test_connection_sync(timeout=0.1)
    assert result is True
    coro = captured.get("coro")
    assert inspect.iscoroutine(coro)
    assert captured["timeout"] == 0.1
    assert run_calls == ["wait-result"]


@pytest.mark.asyncio
async def test_qdrant_connection_tester(monkeypatch):
    client_mock = MagicMock()
    client_mock.async_get_collections = AsyncMock(return_value={})
    client_mock.async_close = AsyncMock()
    client_mock.get_collections.return_value = {}

    def factory(*_, **__):
        return client_mock

    monkeypatch.setattr("app.services.qdrant.QdrantClient", factory)

    tester = QdrantConnectionTester(host="localhost", port=6333)
    assert await tester.test_connection() is True
    client_mock.async_get_collections.assert_awaited()

    assert tester.test_connection_sync() is True
    client_mock.get_collections.assert_called_once()

    await tester.close()
    client_mock.async_close.assert_awaited()
