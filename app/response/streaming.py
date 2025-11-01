from __future__ import annotations

import json
from typing import AsyncIterator, Iterable


class AnswerStreamer:
    """Utility that chunks answers and yields SSE/WebSocket friendly payloads."""

    def __init__(self, *, chunk_size: int = 200) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")

        self.chunk_size = chunk_size

    def chunk_answer(self, text: str) -> Iterable[str]:
        """Split the provided answer into chunks of ``chunk_size`` characters."""

        if not text:
            return []

        return [text[i : i + self.chunk_size] for i in range(0, len(text), self.chunk_size)]

    async def iter_sse(self, text: str) -> AsyncIterator[str]:
        """Yield Server-Sent Event formatted strings for the answer chunks."""

        for index, chunk in enumerate(self.chunk_answer(text)):
            payload = json.dumps({"index": index, "content": chunk})
            yield f"event: chunk\ndata: {payload}\n\n"

        yield "event: end\ndata: {}\n\n"

    async def stream_websocket(self, websocket, text: str) -> None:
        """Send answer chunks over an accepted WebSocket connection."""

        for index, chunk in enumerate(self.chunk_answer(text)):
            await websocket.send_json({"event": "chunk", "index": index, "content": chunk})

        await websocket.send_json({"event": "end"})
