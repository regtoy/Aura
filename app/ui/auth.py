from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.dependencies.auth import Role


@dataclass(frozen=True, slots=True)
class AuthProfile:
    """Streamlit arayüzü için kullanıcı profili."""

    label: str
    username: str
    token: str | None
    roles: tuple[Role, ...]

    def has_role(self, role: Role) -> bool:
        return role in self.roles


_PRESET_PROFILES: tuple[AuthProfile, ...] = (
    AuthProfile("Anonim Kullanıcı", "anonymous", None, (Role.VIEWER,)),
    AuthProfile("Öğrenci (viewer-token)", "viewer", "viewer-token", (Role.VIEWER,)),
    AuthProfile("İdari (editor-token)", "editor", "editor-token", (Role.EDITOR, Role.VIEWER)),
    AuthProfile(
        "Yönetici (admin-token)",
        "admin",
        "admin-token",
        (Role.ADMIN, Role.EDITOR, Role.VIEWER),
    ),
)

_TOKEN_MAP = {profile.token: profile for profile in _PRESET_PROFILES if profile.token}


def preset_profiles() -> Iterable[AuthProfile]:
    """Ön tanımlı profilleri döndür."""

    return _PRESET_PROFILES


def resolve_token(token: str | None) -> AuthProfile | None:
    """Belirtilen token için profili getir."""

    if token is None or token == "":
        return _PRESET_PROFILES[0]
    return _TOKEN_MAP.get(token)
