from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.dependencies.auth import Role, User, role_required
from app.tickets.service import TicketService

require_editor = role_required(Role.EDITOR)
require_viewer = role_required(Role.VIEWER)
require_admin = role_required(Role.ADMIN)

EditorUser = Annotated[User, Depends(require_editor)]
ViewerUser = Annotated[User, Depends(require_viewer)]
AdminUser = Annotated[User, Depends(require_admin)]


async def get_ticket_service(request: Request) -> TicketService:
    service = getattr(request.app.state, "ticket_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Ticket service is not configured")
    return service
