"""Role-based access control middleware for FastAPI."""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.dependencies.auth import User, resolve_user_from_token


class RBACMiddleware(BaseHTTPMiddleware):
    """Populate the request state with the authenticated user."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        authorization = request.headers.get("Authorization")
        token: str | None = None

        if authorization:
            scheme, _, credentials = authorization.partition(" ")
            if scheme.lower() != "bearer":
                return JSONResponse(
                    status_code=401, content={"detail": "Invalid authentication credentials"}
                )
            token = credentials or None

        try:
            user: User = resolve_user_from_token(token)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

        request.state.user = user
        response = await call_next(request)
        return response
