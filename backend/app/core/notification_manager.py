"""
Officer notification persistence (Phase 22).

No event bus, websocket, or SSE mechanism exists anywhere in this
codebase (confirmed during the Phase 22 gap assessment) -- this is a
plain, polling-friendly inbox: `app.core.processing_orchestrator.
ProcessingOrchestrator` creates one `Notification` per (recipient,
finding) pair after a processing run generates or updates a finding, and
an officer's client polls `GET /api/v1/notifications`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Finding, Notification

__all__ = ["NotificationManager"]


class NotificationManager:
    """Service layer for creating and updating officer notifications."""

    @staticmethod
    def notify(db: Session, *, recipient_user_id: int, finding: Finding) -> Notification:
        """Create one notification for `finding`, or return the existing
        unread one for the same recipient (never a duplicate unread
        pointer to the same finding)."""
        existing = (
            db.query(Notification)
            .filter(
                Notification.recipient_user_id == recipient_user_id,
                Notification.finding_id == finding.id,
                Notification.read_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return existing

        notification = Notification(recipient_user_id=recipient_user_id, finding_id=finding.id)
        db.add(notification)
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def list_notifications(
        db: Session, recipient_user_id: int, *, unread_only: bool = False
    ) -> list[Notification]:
        query = db.query(Notification).filter(Notification.recipient_user_id == recipient_user_id)
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        return query.order_by(Notification.created_at.desc()).all()

    @staticmethod
    def get_notification(db: Session, notification_id: int) -> Notification | None:
        return db.query(Notification).filter(Notification.id == notification_id).first()

    @staticmethod
    def mark_read(db: Session, notification: Notification) -> Notification:
        if notification.read_at is None:
            notification.read_at = datetime.now(UTC)
            db.add(notification)
            db.commit()
            db.refresh(notification)
        return notification

    @staticmethod
    def mark_acknowledged(db: Session, notification: Notification) -> Notification:
        now = datetime.now(UTC)
        if notification.read_at is None:
            notification.read_at = now
        if notification.acknowledged_at is None:
            notification.acknowledged_at = now
            db.add(notification)
            db.commit()
            db.refresh(notification)
        return notification
