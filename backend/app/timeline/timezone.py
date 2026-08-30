"""
Generic timezone attachment/conversion (Master Specification Section 26).

Task Phase 11 scope, section 6/17: "Do not hardcode IST into the generic
normalization engine... Use proper timezone support from the existing
Python stack... Do not manually implement DST rules." This module uses
only the stdlib `zoneinfo` module (Python 3.9+) — no vendor/device name is
ever mentioned here; every zone is supplied by the caller as a plain IANA
name string.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class UnknownTimezoneError(ValueError):
    """Raised when a supplied timezone name is not a recognized IANA zone."""


def attach_timezone(naive_timestamp: datetime, timezone_name: str) -> datetime:
    """Interpret a naive datetime as being in the given IANA timezone.

    Args:
        naive_timestamp: A timezone-naive datetime (e.g. a filename-
            derived local recording time). Must not already carry
            timezone info — attaching a second interpretation on top of
            an existing one would silently discard the first, which is
            exactly the kind of fabricated precision task Phase 11 scope
            forbids.
        timezone_name: An IANA timezone name (e.g. `"Asia/Kolkata"`,
            `"UTC"`, `"Etc/GMT-5"`). Resolved via the stdlib `zoneinfo` —
            DST rules, if any, are handled entirely by the platform's
            timezone database, never hand-rolled here.

    Returns:
        A timezone-aware datetime representing the same wall-clock
        reading, now attributed to `timezone_name`.

    Raises:
        ValueError: If `naive_timestamp` already carries timezone info.
        UnknownTimezoneError: If `timezone_name` is not a recognized IANA
            zone name.
    """
    if naive_timestamp.tzinfo is not None:
        raise ValueError(
            f"timestamp {naive_timestamp!r} already carries timezone info "
            f"({naive_timestamp.tzinfo!r}); refusing to reinterpret it under "
            f"{timezone_name!r} rather than silently discarding the existing one"
        )
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise UnknownTimezoneError(f"{timezone_name!r} is not a recognized IANA timezone") from exc
    return naive_timestamp.replace(tzinfo=zone)


def to_utc(aware_timestamp: datetime) -> datetime:
    """Convert a timezone-aware datetime to UTC.

    Args:
        aware_timestamp: A timezone-aware datetime.

    Returns:
        The same instant, represented in UTC.

    Raises:
        ValueError: If `aware_timestamp` is timezone-naive.
    """
    if aware_timestamp.tzinfo is None:
        raise ValueError(
            f"timestamp {aware_timestamp!r} is timezone-naive; call attach_timezone() first "
            "rather than assuming a timezone"
        )
    return aware_timestamp.astimezone(UTC)
