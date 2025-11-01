from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.middleware import RBACMiddleware
from apps.api.routes import answers, ping, tickets
from apps.api.core.config import get_settings
from apps.api.core.logging import configure_logging, init_tracer, shutdown_tracer
from apps.api.services.postgres import PostgresConnectionTester
from apps.api.services.qdrant import QdrantConnectionTester
from apps.api.services.tickets import TicketProcessingPipeline, TicketRepository, TicketService


def _to_asyncpg_dsn(dsn: str) -> str:
    """Ensure the SQLAlchemy DSN uses the asyncpg driver."""

    if dsn.startswith("postgresql+asyncpg://"):
        return dsn
    if dsn.startswith("postgresql://"):
        return "postgresql+asyncpg://" + dsn[len("postgresql://") :]
    return dsn


@asynccontextmanager
def lifespan(app: FastAPI):  # pragma: no cover - executed by framework
    settings = get_settings()
    logger = configure_logging(settings)
    tracer_provider = init_tracer(settings)

    app.state.logger = logger
    app.state.tracer_provider = tracer_provider
    postgres_tester = PostgresConnectionTester(dsn=settings.postgres_dsn)
    qdrant_tester = QdrantConnectionTester(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        api_key=settings.qdrant_api_key,
    )

    app.state.postgres_tester = postgres_tester
    app.state.qdrant_tester = qdrant_tester
    db_engine = None
    app.state.db_engine = None
    app.state.db_session_factory = None
    try:
        await postgres_tester.get_pool()
        db_engine = create_async_engine(_to_asyncpg_dsn(settings.postgres_dsn), future=True)
        session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
        ticket_repository = TicketRepository(session_factory, engine=db_engine)
        await ticket_repository.ensure_schema()
        ticket_pipeline = TicketProcessingPipeline()
        app.state.ticket_service = TicketService(ticket_repository, pipeline=ticket_pipeline)
        app.state.db_engine = db_engine
        app.state.db_session_factory = session_factory
    except Exception:  # pragma: no cover - service initialisation best effort
        app.state.ticket_service = None
        if db_engine is not None:
            await db_engine.dispose()
            db_engine = None
    try:
        yield
    finally:
        if db_engine is not None:
            await db_engine.dispose()
        await postgres_tester.close()
        await qdrant_tester.close()
        shutdown_tracer(tracer_provider)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(RBACMiddleware)
    app.include_router(ping.router)
    app.include_router(answers.router)
    app.include_router(tickets.router)
    return app


app = create_app()
