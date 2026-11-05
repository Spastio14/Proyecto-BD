import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import Principal
from app.models.entities import RegistroAuditoria


class AuditService:
    @staticmethod
    def record(
        session: Session,
        *,
        principal: Principal | None,
        action: str,
        object_type: str,
        object_reference: str,
        reason: str,
        before: Any = None,
        after: Any = None,
    ) -> RegistroAuditoria:
        origin = principal.origin if principal else "SISTEMA"
        actor = principal.persona_id if principal else None
        event = RegistroAuditoria(
            id_persona_actor=actor,
            fecha_hora=datetime.now(UTC),
            accion=action,
            tipo_objeto_afectado=object_type,
            referencia_objeto=object_reference,
            valor_anterior=None
            if before is None
            else json.dumps(before, default=str, ensure_ascii=False),
            valor_nuevo=None
            if after is None
            else json.dumps(after, default=str, ensure_ascii=False),
            motivo=reason,
            origen_accion=origin,
        )
        session.add(event)
        return event
