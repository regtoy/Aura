from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.api.routes import answers, ping, tickets
from apps.api.core.config import get_settings
from apps.api.services.postgres import PostgresConnectionTester
from apps.api.services.qdrant import QdrantConnectionTester
from apps.api.services.tickets import TicketProcessingPipeline, TicketRepository, TicketService


@asynccontextmanager
def lifespan(app: FastAPI):  # pragma: no cover - executed by framework
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
        pool = await postgres_tester.get_pool()
        ticket_repository = TicketRepository(pool)
        await ticket_repository.ensure_schema()
        ticket_pipeline = TicketProcessingPipeline()
        app.state.ticket_service = TicketService(ticket_repository, pipeline=ticket_pipeline)
    except Exception:  # pragma: no cover - service initialisation best effort
        app.state.ticket_service = None
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
