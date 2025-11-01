from collections.abc import Callable
from enum import Enum
from typing import Annotated

from fastapi import Depends, HTTPException, Security
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


bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)]
) -> User:
    """Very small authentication stub.

    For demonstration purposes we simply map a static token to a known user. In a real
    implementation this function would verify the token and fetch the associated user
    from a datastore.
    """

    if credentials is None:
        return User(username="anonymous", roles=(Role.VIEWER,))

    token_map: dict[str, tuple[str, tuple[Role, ...]]] = {
        "admin-token": ("admin", (Role.ADMIN, Role.EDITOR, Role.VIEWER)),
        "editor-token": ("editor", (Role.EDITOR, Role.VIEWER)),
        "viewer-token": ("viewer", (Role.VIEWER,)),
    }

    if credentials.credentials not in token_map:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

    username, roles = token_map[credentials.credentials]
    return User(username=username, roles=roles)


def role_required(role: Role) -> Callable[[User], User]:
    """Dependency factory ensuring the current user has the requested role."""

    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not user.has_role(role):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return dependency


CurrentUser = Annotated[User, Depends(get_current_user)]
