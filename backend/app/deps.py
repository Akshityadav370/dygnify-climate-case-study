from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase

from app.clients.http import UpstreamClient


def get_db(request: Request) -> AsyncDatabase:
    return request.app.state.db


def get_upstream(request: Request) -> UpstreamClient:
    return request.app.state.upstream
