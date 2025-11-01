import pytest
from fastapi import HTTPException

from app.dependencies.auth import Role, User, role_required


@pytest.mark.asyncio
async def test_role_required_allows_authorized_user():
    dependency = role_required(Role.ADMIN)
    user = User("alice", (Role.ADMIN,))
    result = await dependency(user)  # type: ignore[arg-type]
    assert result.username == "alice"


@pytest.mark.asyncio
async def test_role_required_rejects_unauthorized_user():
    dependency = role_required(Role.ADMIN)
    user = User("bob", (Role.VIEWER,))
    with pytest.raises(HTTPException) as exc:
        await dependency(user)  # type: ignore[arg-type]

    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient permissions"
