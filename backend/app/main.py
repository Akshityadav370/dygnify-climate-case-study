import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api import analyze, geocode, meta
from app.clients.http import UpstreamClient
from app.config import Settings, get_settings
from app.db import create_mongo_client, ensure_indexes
from app.errors import install_error_handlers
from app.locks import KeyedLocks
from app.ratelimit import limiter

logging.basicConfig(level=logging.INFO)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        mongo = create_mongo_client(settings)
        app.state.db = mongo[settings.mongo_db]
        app.state.upstream = UpstreamClient(settings)
        app.state.locks = KeyedLocks()
        await ensure_indexes(app.state.db)
        yield
        await app.state.upstream.aclose()
        await mongo.close()

    app = FastAPI(title="Climate Hazard Trend Analyzer API", version="1.0.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.limiter = limiter
    install_error_handlers(app)

    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    app.include_router(meta.router, prefix="/api")
    app.include_router(analyze.router, prefix="/api")
    app.include_router(geocode.router, prefix="/api")
    return app


app = create_app()
