import time as _time
from datetime import datetime, timezone

def now():
    return _time.time()

def sleep(seconds):
    _time.sleep(float(seconds))
    return None

def format_ts(ts=None, fmt="%Y-%m-%d %H:%M:%S"):
    if ts is None:
        ts = _time.time()
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime(str(fmt))

def monotonic():
    return _time.monotonic()
