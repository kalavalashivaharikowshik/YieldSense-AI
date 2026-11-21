from datetime import UTC, datetime


def utc_now_naive() -> datetime:
    """Current UTC time without tzinfo.

    Users, farms, OTPs and reference tables store naive UTC timestamps.
    datetime.utcnow() is deprecated since Python 3.12, so this builds
    the same value from a timezone-aware clock.
    """
    return datetime.now(UTC).replace(tzinfo=None)
