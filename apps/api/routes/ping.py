from fastapi import APIRouter, Depends

from apps.api.dependencies.auth import CurrentUser, Role, role_required

router = APIRouter(prefix="/ping", tags=["health"])


@router.get("", summary="Public health probe")
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/secure",
    summary="RBAC protected endpoint",
    dependencies=[Depends(role_required(Role.EDITOR))],
)
async def secure_ping(user: CurrentUser) -> dict[str, str]:
    return {"status": "ok", "user": user.username}
