import pytest

from apps.api.api.routes import answers


class DummyWebSocket:
    def __init__(self, payload):
        self._payload = payload
        self.accepted = False
        self.sent_messages: list[dict] = []
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def receive_json(self):
        if self._payload is None:
            raise answers.WebSocketDisconnect()
        payload = self._payload
        self._payload = None
        return payload

    async def send_json(self, message):
        self.sent_messages.append(message)

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_compile_answer_route_returns_top_citations():
    request = answers.AnswerCompilationRequest(
        answer="Sample answer",
        documents=[
            answers.RetrievedDocumentModel(document_id="doc-1", score=0.7, metadata={"retriever": "kb"}),
            answers.RetrievedDocumentModel(document_id="doc-2", score=0.9, metadata={"source": "web"}),
        ],
    )

    response = await answers.compile_answer(request)
    assert response.answer == "Sample answer"
    assert [item.document_id for item in response.citations] == ["doc-2", "doc-1"]
    assert response.citations[0].route == "web"


@pytest.mark.asyncio
async def test_stream_answer_sse_endpoint_emits_chunk_events():
    streaming_response = await answers.stream_answer(text="Merhaba Dünya", chunk_size=7)

    chunks: list[str] = []

    async for chunk in streaming_response.body_iterator:  # type: ignore[attr-defined]
        chunks.append(chunk if isinstance(chunk, str) else chunk.decode())

    body = "".join(chunks)
    assert "event: chunk" in body
    assert "Merhaba" in body
    assert "event: end" in body


@pytest.mark.asyncio
async def test_stream_answer_websocket_sends_chunks_and_end_event():
    websocket = DummyWebSocket({"text": "agentic", "chunk_size": 3})
    await answers.stream_answer_websocket(websocket)

    assert websocket.accepted is True
    assert websocket.closed is True
    assert websocket.sent_messages == [
        {"event": "chunk", "index": 0, "content": "age"},
        {"event": "chunk", "index": 1, "content": "nti"},
        {"event": "chunk", "index": 2, "content": "c"},
        {"event": "end"},
    ]
