from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.dependencies.tickets import EditorUser, ViewerUser, get_ticket_service
from app.tickets.models import Ticket, TicketAuditEntry
from app.tickets.service import InvalidTicketTransitionError, TicketNotFoundError, TicketService
from app.tickets.state import TicketStatus

router = APIRouter(prefix="/tickets", tags=["tickets"])


class TicketCreateRequest(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)


class TicketUpdateRequest(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, min_length=1)

    def ensure_payload(self) -> None:
        if self.subject is None and self.description is None:
            raise HTTPException(status_code=400, detail="No fields provided for update")


class TicketStatusChangeRequest(BaseModel):
    status: TicketStatus
    note: str | None = Field(default=None, max_length=500)
    metadata: dict[str, str] | None = Field(default=None)


class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject: str
    description: str
    normalized_description: str
    embedding: list[float]
    status: TicketStatus
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime


class TicketAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ticket_id: UUID
    from_status: TicketStatus | None
    to_status: TicketStatus
    actor: str
    note: str
    metadata: dict[str, str]
    created_at: datetime


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]


def _to_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse.model_validate(ticket)


def _to_audit_response(entry: TicketAuditEntry) -> TicketAuditResponse:
    return TicketAuditResponse.model_validate(entry)


@router.post("", response_model=TicketResponse, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateRequest,
    service: TicketServiceDep,
    user: EditorUser,
) -> TicketResponse:
    ticket = await service.create_ticket(subject=payload.subject, description=payload.description, actor=user.username)
    return _to_response(ticket)


@router.get("", response_model=list[TicketResponse])
async def list_tickets(
    service: TicketServiceDep,
    _: ViewerUser,
    status_filter: TicketStatus | None = Query(default=None, alias="status"),
) -> list[TicketResponse]:
    tickets = await service.list_tickets(status=status_filter)
    return [_to_response(ticket) for ticket in tickets]


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: UUID, service: TicketServiceDep, _: ViewerUser) -> TicketResponse:
    try:
        ticket = await service.get_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(ticket)


@router.put("/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: UUID,
    payload: TicketUpdateRequest,
    service: TicketServiceDep,
    user: EditorUser,
) -> TicketResponse:
    payload.ensure_payload()
    try:
        ticket = await service.update_ticket(
            ticket_id,
            subject=payload.subject,
            description=payload.description,
            actor=user.username,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _to_response(ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: UUID, service: TicketServiceDep, user: EditorUser) -> None:
    try:
        await service.delete_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{ticket_id}/status", response_model=TicketResponse)
async def change_ticket_status(
    ticket_id: UUID,
    payload: TicketStatusChangeRequest,
    service: TicketServiceDep,
    user: EditorUser,
) -> TicketResponse:
    try:
        ticket = await service.change_status(
            ticket_id,
            new_status=payload.status,
            actor=user.username,
            note=payload.note or "Status updated",
            metadata=payload.metadata,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidTicketTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _to_response(ticket)


@router.get("/{ticket_id}/audit", response_model=list[TicketAuditResponse])
async def get_ticket_audit(ticket_id: UUID, service: TicketServiceDep, _: ViewerUser) -> list[TicketAuditResponse]:
    entries = await service.get_audit_log(ticket_id)
    return [_to_audit_response(entry) for entry in entries]
