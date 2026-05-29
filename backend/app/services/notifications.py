"""
Central notification service.
Call notify() or the typed helpers from API handlers after commits.
"""
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notification import Notification
from app.models.user import User, UserRole
from app.models.user_role import UserRoleEntry


async def notify(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[uuid.UUID] = None,
) -> None:
    db.add(Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    ))


async def notify_role(
    db: AsyncSession,
    role: str,
    type: str,
    title: str,
    body: Optional[str] = None,
    link: Optional[str] = None,
    related_entity_type: Optional[str] = None,
    related_entity_id: Optional[uuid.UUID] = None,
    exclude_user_id: Optional[uuid.UUID] = None,
) -> None:
    """Notify all active users with the given role."""
    rows = (await db.execute(
        select(User.id)
        .join(UserRoleEntry, UserRoleEntry.user_id == User.id)
        .where(UserRoleEntry.role == role, User.is_active == True)
    )).scalars().all()
    for uid in rows:
        if exclude_user_id and uid == exclude_user_id:
            continue
        await notify(db, uid, type, title, body, link, related_entity_type, related_entity_id)


# ─── Typed helpers ────────────────────────────────────────────────────────────

async def on_reimbursement_created(
    db: AsyncSession, expense_id: uuid.UUID, amount_cny: str, creator_name: str,
) -> None:
    body = f"{creator_name} · {amount_cny} CNY"
    link = f"/expenses/{expense_id}"
    for role in ("admin", "accountant"):
        await notify_role(db, role, "reimbursement_created", "reimbursement_created",
                          body, link, "expense", expense_id)


async def on_reimbursement_status_changed(
    db: AsyncSession, expense_id: uuid.UUID, creator_id: uuid.UUID,
    new_status: str, amount_cny: str,
) -> None:
    status_map = {
        "approved": "reimbursement_approved",
        "rejected": "reimbursement_rejected",
        "paid":     "reimbursement_paid",
    }
    if new_status not in status_map:
        return
    n_type = status_map[new_status]
    await notify(db, creator_id, n_type, n_type,
                 f"{amount_cny} CNY", f"/expenses/{expense_id}",
                 "expense", expense_id)


async def on_order_paid(
    db: AsyncSession, order_id: uuid.UUID, order_number: str,
    manager_id: uuid.UUID, client_name: str, amount_cny: str,
) -> None:
    body = f"{order_number} · {client_name} · {amount_cny} CNY"
    link = f"/orders/{order_id}"
    await notify(db, manager_id, "order_paid", "order_paid", body, link, "order", order_id)
    for role in ("accountant", "admin"):
        await notify_role(db, role, "order_paid", "order_paid", body, link,
                          "order", order_id, exclude_user_id=manager_id)


async def on_purchase_created(
    db: AsyncSession, purchase_id: uuid.UUID, purchase_number: str,
    manager_id: Optional[uuid.UUID],
) -> None:
    if not manager_id:
        return
    await notify(db, manager_id, "purchase_created", "purchase_created",
                 purchase_number, f"/purchases/{purchase_id}",
                 "purchase", purchase_id)


async def on_purchase_paid(
    db: AsyncSession, purchase_id: uuid.UUID, purchase_number: str,
    purchaser_id: Optional[uuid.UUID], amount_cny: str,
) -> None:
    body = f"{purchase_number} · {amount_cny} CNY"
    link = f"/purchases/{purchase_id}"
    if purchaser_id:
        await notify(db, purchaser_id, "purchase_paid", "purchase_paid", body, link,
                     "purchase", purchase_id)
    for role in ("accountant", "admin"):
        await notify_role(db, role, "purchase_paid", "purchase_paid", body, link,
                          "purchase", purchase_id,
                          exclude_user_id=purchaser_id)


async def on_payment_unassigned(
    db: AsyncSession, payment_id: uuid.UUID, amount: str, currency: str, cp_name: str,
) -> None:
    body = f"{cp_name} · {amount} {currency}"
    link = f"/payments/{payment_id}"
    await notify_role(db, "accountant", "payment_unassigned", "payment_unassigned",
                      body, link, "payment", payment_id)
