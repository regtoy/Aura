from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from apps.api.dependencies.auth import CurrentUser, User
from apps.api.services.tickets import (
    Ticket,
    TicketAggregate,
    TicketMessage,
    TicketNotFoundError,
    TicketService,
    TicketStatus,
)


router = APIRouter(prefix="/tickets", tags=["tickets"])


async def get_ticket_service(request: Request) -> TicketService:
    service = getattr(request.app.state, "ticket_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Ticket service is not available")
    return service


TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]


class TicketMessageModel(BaseModel):
    id: str
    author: str
    content: str
    normalized_content: str
    embedding: list[float] = Field(default_factory=list)
    created_at: str

    @classmethod
    def from_entity(cls, entity: TicketMessage) -> "TicketMessageModel":
        return cls(
            id=entity.id,
            author=entity.author,
            content=entity.content,
            normalized_content=entity.normalized_content,
            embedding=[float(value) for value in entity.embedding],
            created_at=entity.created_at.isoformat(),
        )


class TicketAuditLogModel(BaseModel):
    id: str
    action: str
    actor: str
    from_status: TicketStatus | None = None
    to_status: TicketStatus | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class TicketModel(BaseModel):
    id: str
    title: str
    status: TicketStatus
    priority: str
    requester: str
    metadata: dict[str, Any]
    created_at: str
    updated_at: str


class TicketDetailModel(TicketModel):
    messages: list[TicketMessageModel]
    audit_logs: list[TicketAuditLogModel]

    @classmethod
    def from_aggregate(cls, aggregate: TicketAggregate) -> "TicketDetailModel":
        return cls(
            id=aggregate.ticket.id,
            title=aggregate.ticket.title,
            status=aggregate.ticket.status,
            priority=aggregate.ticket.priority,
            requester=aggregate.ticket.requester,
            metadata=dict(aggregate.ticket.metadata),
            created_at=aggregate.ticket.created_at.isoformat(),
            updated_at=aggregate.ticket.updated_at.isoformat(),
            messages=[TicketMessageModel.from_entity(message) for message in aggregate.messages],
            audit_logs=[
                TicketAuditLogModel(
                    id=log.id,
                    action=log.action,
                    actor=log.actor,
                    from_status=log.from_status,
                    to_status=log.to_status,
                    metadata=dict(log.metadata),
                    created_at=log.created_at.isoformat(),
                )
                for log in aggregate.audit_logs
            ],
        )


class TicketCreateRequest(BaseModel):
    title: str
    content: str
    priority: str = Field(default="medium")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketStatusChangeRequest(BaseModel):
    status: TicketStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketMessageCreateRequest(BaseModel):
    content: str


def _ticket_to_model(ticket: Ticket) -> TicketModel:
    return TicketModel(
        id=ticket.id,
        title=ticket.title,
        status=ticket.status,
        priority=ticket.priority,
        requester=ticket.requester,
        metadata=dict(ticket.metadata),
        created_at=ticket.created_at.isoformat(),
        updated_at=ticket.updated_at.isoformat(),
    )


@router.get("", response_model=list[TicketModel], summary="List existing tickets")
async def list_tickets(service: TicketServiceDep) -> list[TicketModel]:
    tickets = await service.list_tickets()
    return [_ticket_to_model(item) for item in tickets]


@router.post("", response_model=TicketDetailModel, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreateRequest,
    service: TicketServiceDep,
    user: CurrentUser,
) -> TicketDetailModel:
    aggregate = await service.create_ticket(
        title=payload.title,
        content=payload.content,
        requester=user.username,
        priority=payload.priority,
        metadata=payload.metadata,
    )
    return TicketDetailModel.from_aggregate(aggregate)


@router.get("/{ticket_id}", response_model=TicketDetailModel)
async def get_ticket(ticket_id: str, service: TicketServiceDep) -> TicketDetailModel:
    try:
        aggregate = await service.get_ticket(ticket_id)
    except TicketNotFoundError as exc:  # pragma: no cover - defensive guard
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TicketDetailModel.from_aggregate(aggregate)


@router.post("/{ticket_id}/messages", response_model=TicketDetailModel, status_code=status.HTTP_201_CREATED)
async def add_ticket_message(
    ticket_id: str,
    payload: TicketMessageCreateRequest,
    service: TicketServiceDep,
    user: CurrentUser,
) -> TicketDetailModel:
    try:
        aggregate = await service.add_message(ticket_id, content=payload.content, author=user.username)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return TicketDetailModel.from_aggregate(aggregate)


@router.post("/{ticket_id}/status", response_model=TicketDetailModel)
async def change_ticket_status(
    ticket_id: str,
    payload: TicketStatusChangeRequest,
    service: TicketServiceDep,
    user: CurrentUser,
) -> TicketDetailModel:
    try:
        aggregate = await service.change_status(
            ticket_id,
            new_status=payload.status,
            actor=user.username,
            metadata=payload.metadata,
        )
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TicketDetailModel.from_aggregate(aggregate)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: str, service: TicketServiceDep) -> None:
    try:
        await service.delete_ticket(ticket_id)
    except TicketNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
