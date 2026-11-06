from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import Principal, get_principal
from app.db.session import get_session
from app.services.reports import ReportService

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/resumen")
def dashboard(
    principal: Principal = Depends(get_principal), session: Session = Depends(get_session)
) -> dict[str, object]:
    return ReportService.dashboard(session, principal)
