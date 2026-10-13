from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.deps import get_db

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(db=Depends(get_db)):
    try:
        await db.command("ping")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "db": "unreachable"})
    return {"status": "ok", "db": "ok"}
