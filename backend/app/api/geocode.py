from typing import Literal

from fastapi import APIRouter, Depends, Query, Request

from app.deps import get_db, get_upstream
from app.errors import BadRequestError
from app.models import GeocodeResponse
from app.ratelimit import GEOCODE_LIMIT, limiter
from app.services.geocode import geocode

router = APIRouter(tags=["geocode"])


@router.get("/geocode", response_model=GeocodeResponse)
@limiter.limit(GEOCODE_LIMIT)
async def search_places(
    request: Request,
    q: str = Query(max_length=100, description="Place name"),
    kind: Literal["city", "state"] = "city",
    db=Depends(get_db),
    upstream=Depends(get_upstream),
):
    q = q.strip()
    if len(q) < 2:
        raise BadRequestError("Search text must be at least 2 characters.")
    return {"results": await geocode(db, upstream, request.app.state.settings, q, kind)}
