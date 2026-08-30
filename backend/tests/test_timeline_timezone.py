"""Tests for generic timezone attachment/conversion (app/timeline/timezone.py), Phase 11."""

from __future__ import annotations

import datetime

import pytest

from app.timeline.timezone import UnknownTimezoneError, attach_timezone, to_utc


def test_attach_timezone_utc():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    aware = attach_timezone(naive, "UTC")
    assert aware.utcoffset() == datetime.timedelta(0)
    assert aware.replace(tzinfo=None) == naive


def test_attach_timezone_ist_asia_kolkata():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    aware = attach_timezone(naive, "Asia/Kolkata")
    assert aware.utcoffset() == datetime.timedelta(hours=5, minutes=30)


def test_attach_timezone_other_named_zone_new_york():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    aware = attach_timezone(naive, "America/New_York")
    # August is EDT (UTC-4) in America/New_York — proves this isn't IST-specific.
    assert aware.utcoffset() == datetime.timedelta(hours=-4)


def test_attach_timezone_fixed_offset_zone():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    aware = attach_timezone(naive, "Etc/GMT-5")  # POSIX sign is inverted: GMT-5 == UTC+5
    assert aware.utcoffset() == datetime.timedelta(hours=5)


def test_attach_timezone_rejects_already_aware_input():
    aware = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=datetime.UTC)
    with pytest.raises(ValueError, match="already carries timezone"):
        attach_timezone(aware, "Asia/Kolkata")


def test_attach_timezone_rejects_unknown_zone_name():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    with pytest.raises(UnknownTimezoneError):
        attach_timezone(naive, "Not/A_Real_Zone")


def test_to_utc_converts_ist_correctly():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    aware = attach_timezone(naive, "Asia/Kolkata")
    utc = to_utc(aware)
    assert utc == datetime.datetime(2026, 8, 28, 10, 50, 0, tzinfo=datetime.UTC)


def test_to_utc_is_identity_for_already_utc_input():
    aware = datetime.datetime(2026, 8, 28, 16, 20, 0, tzinfo=datetime.UTC)
    assert to_utc(aware) == aware


def test_to_utc_rejects_naive_input():
    naive = datetime.datetime(2026, 8, 28, 16, 20, 0)
    with pytest.raises(ValueError, match="timezone-naive"):
        to_utc(naive)
