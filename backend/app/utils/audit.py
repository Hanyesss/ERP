"""Universal audit log helper — call after any create/update/delete."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog, AuditActionEnum


async def write_audit(
    db: AsyncSession,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: AuditActionEnum,
    changes: dict | None = None,
) -> None:
    db.add(AuditLog(
        id=uuid.uuid4(),
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        changes=changes,
    ))
