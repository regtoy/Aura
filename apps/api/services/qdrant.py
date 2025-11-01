from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import QdrantClient


@dataclass(slots=True)
class QdrantConnectionTester:
    """Utility that checks connectivity with a Qdrant instance."""

    host: str
    port: int
    api_key: str | None = None
    _client: QdrantClient | None = None

    def _ensure_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key,
                timeout=2.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.async_close()
            self._client = None

    async def test_connection(self) -> bool:
        client = self._ensure_client()
        await client.async_get_collections()
        return True

    def test_connection_sync(self) -> bool:
        client = self._ensure_client()
        client.get_collections()
        return True
