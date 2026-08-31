"""
API routes for the officer notification inbox (Phase 22).
Task Phase 22 scope, "API": `GET /notifications`,
`PATCH /notifications/{notification_id}`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.findings import _finding_response
from app.core.notification_manager import NotificationManager
from app.models import Notification, User
from app.schemas.notification import NotificationResponse, NotificationUpdateRequest
from app.storage.db import get_db

router = APIRouter()


def _notification_response(db: Session, notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        recipient_user_id=notification.recipient_user_id,
        finding_id=notification.finding_id,
        created_at=notification.created_at,
        read_at=notification.read_at,
        acknowledged_at=notification.acknowledged_at,
        finding=_finding_response(db, notification.finding),
    )


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[NotificationResponse]:
    """List the authenticated officer's own notifications, newest first.

    Scoped strictly to `current_user` -- an officer can never list
    another user's notifications through this endpoint (task Phase 22
    scope, "Security": "Do not leak evidence metadata to unauthorized
    users").
    """
    notifications = NotificationManager.list_notifications(
        db, current_user.id, unread_only=unread_only
    )
    return [_notification_response(db, n) for n in notifications]


@router.patch("/notifications/{notification_id}", response_model=NotificationResponse)
def update_notification(
    notification_id: int,
    request: NotificationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NotificationResponse:
    """Mark one of the authenticated officer's own notifications read/acknowledged."""
    notification = NotificationManager.get_notification(db, notification_id)
    if notification is None or notification.recipient_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification with id {notification_id} not found",
        )
    if request.acknowledged:
        notification = NotificationManager.mark_acknowledged(db, notification)
    elif request.read:
        notification = NotificationManager.mark_read(db, notification)
    return _notification_response(db, notification)
