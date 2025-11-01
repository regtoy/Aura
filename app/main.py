from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import answers, ping, tickets
from app.core.config import get_settings
from app.services.postgres import PostgresConnectionTester
from app.services.qdrant import QdrantConnectionTester


@asynccontextmanager
async def lifespan(app: FastAPI):  # pragma: no cover - executed by framework
    settings = get_settings()
    postgres_tester = PostgresConnectionTester(dsn=settings.postgres_dsn)
    qdrant_tester = QdrantConnectionTester(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )

    app.state.postgres_tester = postgres_tester
    app.state.qdrant_tester = qdrant_tester
    try:
        yield
    finally:
        await postgres_tester.close()
        await qdrant_tester.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.include_router(ping.router)
    app.include_router(answers.router)
    app.include_router(tickets.router)
    return app


app = create_app()
