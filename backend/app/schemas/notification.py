"""
Pydantic schemas for the officer notification API (Phase 22).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.finding import FindingResponse


class NotificationResponse(BaseModel):
    """One notification, with its authoritative `Finding` embedded read-only
    (task Phase 22 scope, "Notification Model": the notification itself
    never duplicates finding content -- this embeds a read of it, it does
    not store a second copy)."""

    id: int
    recipient_user_id: int
    finding_id: int
    created_at: datetime
    read_at: datetime | None
    acknowledged_at: datetime | None
    finding: FindingResponse


class NotificationUpdateRequest(BaseModel):
    """Mark a notification read and/or acknowledged."""

    read: bool = Field(default=True, description="Mark as read.")
    acknowledged: bool = Field(default=False, description="Mark as acknowledged.")
