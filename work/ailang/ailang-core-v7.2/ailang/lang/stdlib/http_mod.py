"""Cliente HTTP mínimo (urllib)."""
from __future__ import annotations
import json as _json
import urllib.request
import urllib.error


def get(url, headers=None, timeout=30):
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
    r = get(url, **kw)
    try:
        r["json"] = _json.loads(r.get("body") or "null")
    except Exception:
        r["json"] = None
    return r
