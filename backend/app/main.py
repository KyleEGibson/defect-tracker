"""uvicorn app.main:create_app --factory --reload"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from . import __version__
from .config import Settings
from .models import Base
from .routers import auth, defects, metrics


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    settings.check()

    url = settings.database_url
    if url.startswith("sqlite"):
        # in-memory SQLite must share one connection across threads
        extra = {"poolclass": StaticPool} if url in ("sqlite://", "sqlite:///:memory:") else {}
        engine = create_engine(url, connect_args={"check_same_thread": False}, **extra)
    else:
        engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)

    app = FastAPI(title="Defect & CAPA Tracker", version=__version__,
                  description="Defects, root cause and corrective action workflow with an audit trail.")
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker(bind=engine, expire_on_commit=False)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
    for router in (auth.router, defects.router, metrics.router):
        app.include_router(router, prefix="/api")

    @app.get("/api/health", tags=["health"])
    def health():
        return {"status": "ok", "version": __version__}

    if settings.seed_demo:
        from .seed import seed_if_empty
        with app.state.sessionmaker() as db:
            seed_if_empty(db)
    return app

