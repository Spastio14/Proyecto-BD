from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.services.reports import ReportService

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/resumen")
def dashboard(
    days: int = Query(default=30, ge=1, le=3650),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return ReportService.dashboard(session, principal, days=days)
