from collections.abc import Callable
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


class Role(str, Enum):
    """Supported roles."""

    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class User:
    """Simple representation of an authenticated user."""

    def __init__(self, username: str, roles: tuple[Role, ...]):
        self.username = username
        self.roles = roles

    def has_role(self, role: Role) -> bool:
        return role in self.roles


TOKEN_USER_MAP: dict[str, tuple[str, tuple[Role, ...]]] = {
    "admin-token": ("admin", (Role.ADMIN, Role.EDITOR, Role.VIEWER)),
    "editor-token": ("editor", (Role.EDITOR, Role.VIEWER)),
    "viewer-token": ("viewer", (Role.VIEWER,)),
}

bearer_scheme = HTTPBearer(auto_error=False)


def resolve_user_from_token(token: str | None) -> User:
    """Return a user instance associated with the provided bearer token."""

    if token is None:
        return User(username="anonymous", roles=(Role.VIEWER,))

    if token not in TOKEN_USER_MAP:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    username, roles = TOKEN_USER_MAP[token]
    return User(username=username, roles=roles)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)],
    request: Request,
) -> User:
    """Very small authentication stub.

    For demonstration purposes we simply map a static token to a known user. In a real
    implementation this function would verify the token and fetch the associated user
    from a datastore.
    """

    cached = getattr(request.state, "user", None)
    if isinstance(cached, User):
        return cached

    token = credentials.credentials if credentials is not None else None
    user = resolve_user_from_token(token)
    request.state.user = user
    return user


def role_required(role: Role) -> Callable[[User], User]:
    """Dependency factory ensuring the current user has the requested role."""

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not user.has_role(role):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
