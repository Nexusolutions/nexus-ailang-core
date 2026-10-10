"""Stdlib `http` — cliente HTTP con capability enforcement (P3-9b).

Cada operación requiere `network.http` capability.
"""
from __future__ import annotations
import json as _json
import urllib.request
import urllib.error

from ailang.runtime.capabilities import require


def get(url, headers=None, timeout=30):
    """HTTP GET. Requiere capability `network.http`."""
    require("network.http", op_desc=f"http.get({url!r})")
    req = urllib.request.Request(str(url), headers=dict(headers or {}), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "error": str(e)}
    except Exception as e:
        return {"status": 0, "body": "", "error": str(e)}


def post(url, data=None, headers=None, timeout=30):
    """HTTP POST. Requiere capability `network.http`."""
    require("network.http", op_desc=f"http.post({url!r}, ...)")
    h = dict(headers or {})
    payload = None
    if data is not None:
        if isinstance(data, (dict, list)):
            payload = _json.dumps(data).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        else:
            payload = str(data).encode("utf-8")
    req = urllib.request.Request(str(url), data=payload, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "error": str(e)}
    except Exception as e:
        return {"status": 0, "body": "", "error": str(e)}


def json_get(url, **kw):
    """HTTP GET + parse JSON. Requiere capability `network.http`."""
    require("network.http", op_desc=f"http.json_get({url!r})")
    r = get(url, **kw)
    try:
        r["json"] = _json.loads(r.get("body") or "null")
    except Exception:
        r["json"] = None
    return r
