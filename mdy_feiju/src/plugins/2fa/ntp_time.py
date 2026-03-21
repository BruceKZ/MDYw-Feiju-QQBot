"""
Time helper for 2FA TOTP generation.

Uses local system time directly (no NTP).
"""

import time
from datetime import datetime
from zoneinfo import ZoneInfo


def get_accurate_time() -> float:
    """Returns current unix timestamp from local clock."""
    return time.time()


def get_accurate_datetime_shanghai() -> datetime:
    """Returns current datetime in Asia/Shanghai timezone."""
    return datetime.now(tz=ZoneInfo("Asia/Shanghai"))


def get_totp_code(secret: str) -> tuple[str, int]:
    """
    Generate TOTP code using local system time.
    Returns (code, remaining_seconds).
    """
    import pyotp
    totp = pyotp.TOTP(secret)
    ts = time.time()
    code = totp.at(ts)
    remaining = int(totp.interval - (ts % totp.interval))
    return code, remaining
