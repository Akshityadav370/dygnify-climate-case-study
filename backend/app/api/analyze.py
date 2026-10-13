from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from app.deps import get_db, get_upstream
from app.models import AnalysisOut, AnalyzeRequest
from app.ratelimit import ANALYZE_LIMIT, EXPORT_LIMIT, READ_LIMIT, limiter
from app.services.analysis import get_analysis, get_or_create_analysis
from app.services.export import to_csv, to_pdf

router = APIRouter(tags=["analysis"])

CACHE_CONTROL = "public, max-age=86400"
AnalysisId = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$", description="Analysis id (sha256 hex)")]


@router.post("/analyze", response_model=AnalysisOut)
@limiter.limit(ANALYZE_LIMIT)
async def analyze(request: Request, body: AnalyzeRequest, db=Depends(get_db), upstream=Depends(get_upstream)):
    state = request.app.state
    return await get_or_create_analysis(db, upstream, state.locks, state.settings, body)


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
@limiter.limit(READ_LIMIT)
async def read_analysis(request: Request, response: Response, analysis_id: AnalysisId, db=Depends(get_db)):
    response.headers["Cache-Control"] = CACHE_CONTROL
    return await get_analysis(db, analysis_id)


@router.get("/analyses/{analysis_id}/export.csv")
@limiter.limit(EXPORT_LIMIT)
async def export_csv(request: Request, analysis_id: AnalysisId, db=Depends(get_db)):
    analysis = await get_analysis(db, analysis_id)
    return Response(
        content=to_csv(analysis),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="heatwave-{analysis_id[:8]}.csv"',
            "Cache-Control": CACHE_CONTROL,
        },
    )


@router.get("/analyses/{analysis_id}/report.pdf")
@limiter.limit(EXPORT_LIMIT)
async def export_pdf(request: Request, analysis_id: AnalysisId, db=Depends(get_db)):
    analysis = await get_analysis(db, analysis_id)
    return Response(
        content=to_pdf(analysis),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="heatwave-{analysis_id[:8]}.pdf"',
            "Cache-Control": CACHE_CONTROL,
        },
    )
