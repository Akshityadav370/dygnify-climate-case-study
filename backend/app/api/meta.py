from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.config import DATA_START_YEAR, last_complete_year
from app.deps import get_db
from app.ratelimit import READ_LIMIT, limiter

router = APIRouter(tags=["meta"])

HAZARDS = [
    {
        "id": "heatwave",
        "name": "Heatwave",
        "status": "available",
        "definition": "3+ consecutive days with daily maximum temperature above the local 95th percentile "
        "(1981–2010 baseline, ±7-day window).",
    },
    {"id": "heavy_rainfall", "name": "Heavy rainfall", "status": "coming_soon", "definition": None},
    {"id": "drought", "name": "Drought", "status": "coming_soon", "definition": None},
]


@router.get("/health")
async def health(db=Depends(get_db)):
    try:
        await db.command("ping")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})
    return {"status": "ok", "db": "ok"}


@router.get("/hazards")
@limiter.limit(READ_LIMIT)
async def hazards(request: Request):
    return {"hazards": HAZARDS, "years": {"min": DATA_START_YEAR, "max": last_complete_year()}}
