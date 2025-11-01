import sys
import types

import pytest


@pytest.fixture(scope="session", autouse=True)
def stub_external_dependencies():
    if "asyncpg" not in sys.modules:
        asyncpg_module = types.ModuleType("asyncpg")
        asyncpg_module.create_pool = None
        sys.modules["asyncpg"] = asyncpg_module

    try:  # pragma: no cover - fall back when FastAPI is unavailable
        import fastapi  # type: ignore
    except ModuleNotFoundError:
        fastapi_module = types.ModuleType("fastapi")

        class HTTPException(Exception):
            def __init__(self, status_code: int, detail: str):
                super().__init__(detail)
                self.status_code = status_code
                self.detail = detail

        class Depends:
            def __init__(self, dependency):
                self.dependency = dependency

        class Security:
            def __init__(self, scheme):
                self.scheme = scheme

        fastapi_module.HTTPException = HTTPException
        fastapi_module.Depends = Depends
        fastapi_module.Security = Security

        security_module = types.ModuleType("fastapi.security")

        class HTTPAuthorizationCredentials:
            def __init__(self, scheme: str = "Bearer", credentials: str | None = None):
                self.scheme = scheme
                self.credentials = credentials or ""

        class HTTPBearer:
            def __init__(self, auto_error: bool = True):
                self.auto_error = auto_error

            async def __call__(self):
                return None

        security_module.HTTPAuthorizationCredentials = HTTPAuthorizationCredentials
        security_module.HTTPBearer = HTTPBearer

        fastapi_module.security = security_module

        sys.modules["fastapi"] = fastapi_module
        sys.modules["fastapi.security"] = security_module
    yield
