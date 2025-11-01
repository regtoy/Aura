from __future__ import annotations

from typing import Any, Iterable

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.response import AnswerStreamer, ResponseCompiler, RetrievedDocument

router = APIRouter(prefix="/answers", tags=["answers"])


class RetrievedDocumentModel(BaseModel):
    document_id: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerCompilationRequest(BaseModel):
    answer: str
    documents: list[RetrievedDocumentModel] = Field(default_factory=list)


class CitationModel(BaseModel):
    document_id: str
    route: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnswerCompilationResponse(BaseModel):
    answer: str
    citations: list[CitationModel]


compiler = ResponseCompiler()


def _convert_documents(payload: Iterable[RetrievedDocumentModel]) -> list[RetrievedDocument]:
    return [
        RetrievedDocument(
            document_id=document.document_id,
            score=document.score,
            metadata=document.metadata,
        )
        for document in payload
    ]


@router.post("", response_model=AnswerCompilationResponse, summary="Compile answer with citations")
async def compile_answer(request: AnswerCompilationRequest) -> AnswerCompilationResponse:
    compiled = compiler.compile(answer=request.answer, documents=_convert_documents(request.documents))
    citations = [
        CitationModel(
            document_id=item.document_id,
            route=item.route,
            score=item.score,
            metadata=dict(item.metadata),
        )
        for item in compiled.citations
    ]
    return AnswerCompilationResponse(answer=compiled.answer, citations=citations)


@router.get(
    "/stream",
    response_class=StreamingResponse,
    summary="Stream answer chunks via Server-Sent Events",
)
async def stream_answer(
    text: str = Query("", description="Answer text to stream"),
    chunk_size: int = Query(200, ge=1, le=2000, description="Character length per chunk"),
) -> StreamingResponse:
    streamer = AnswerStreamer(chunk_size=chunk_size)
    return StreamingResponse(streamer.iter_sse(text), media_type="text/event-stream")


@router.websocket("/ws")
async def stream_answer_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        initial = await websocket.receive_json()
    except WebSocketDisconnect:  # pragma: no cover - defensive guard
        return

    text = str(initial.get("text", ""))
    chunk_size = initial.get("chunk_size")
    try:
        chunk_size_int = int(chunk_size) if chunk_size is not None else 200
    except (TypeError, ValueError):
        chunk_size_int = 200

    if chunk_size_int < 1:
        chunk_size_int = 1
    elif chunk_size_int > 2000:
        chunk_size_int = 2000

    streamer = AnswerStreamer(chunk_size=chunk_size_int)

    try:
        await streamer.stream_websocket(websocket, text)
    except WebSocketDisconnect:  # pragma: no cover - connection closed by client
        return
    finally:
        await websocket.close()
