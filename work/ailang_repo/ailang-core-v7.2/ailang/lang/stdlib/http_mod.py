"""Stdlib `http` — cliente HTTP con capability enforcement (P3-9b).

Cada operación requiere `network.http` capability.

AUD-075: URL validation. Se rechazan esquemas no HTTP/HTTPS para prevenir
SSRF (Server-Side Request Forgery) — `file:///etc/passwd`, `ftp://`, etc.
"""
from __future__ import annotations
import json as _json
import urllib.request
import urllib.error
import urllib.parse

from ailang.runtime.capabilities import require
from ailang.lang.errors import AILangRuntimeError


# Esquemas permitidos. Solo http y https para prevenir SSRF.
_ALLOWED_SCHEMES = {"http", "https"}


def _validate_url(url) -> str:
    """Valida que la URL use un esquema HTTP/HTTPS.

    AUD-075: previene SSRF rechazando `file://`, `ftp://`, `gopher://`, etc.
    """
    url_str = str(url)
    if not url_str:
        raise AILangRuntimeError(
            "URL vacía", code="E062",
        )

    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception as e:
        raise AILangRuntimeError(
            f"URL inválida: {url_str!r} ({e})", code="E062",
        )

    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise AILangRuntimeError(
            f"esquema no permitido: {scheme!r}. Solo http/https están soportados "
            f"(URL: {url_str!r})",
            code="E062",
        )

    if not parsed.netloc:
        raise AILangRuntimeError(
            f"URL sin host: {url_str!r}", code="E062",
        )

    return url_str


def get(url, headers=None, timeout=30):
    """HTTP GET. Requiere capability `network.http`.

    AUD-075: valida esquema de la URL (solo http/https).
    """
    require("network.http", op_desc=f"http.get({url!r})")
    safe_url = _validate_url(url)
    req = urllib.request.Request(safe_url, headers=dict(headers or {}), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "error": str(e)}
    except Exception as e:
        return {"status": 0, "body": "", "error": str(e)}


def post(url, data=None, headers=None, timeout=30):
    """HTTP POST. Requiere capability `network.http`.

    AUD-075: valida esquema de la URL (solo http/https).
    """
    require("network.http", op_desc=f"http.post({url!r}, ...)")
    safe_url = _validate_url(url)
    h = dict(headers or {})
    payload = None
    if data is not None:
        if isinstance(data, (dict, list)):
            payload = _json.dumps(data).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        else:
            payload = str(data).encode("utf-8")
    req = urllib.request.Request(safe_url, data=payload, headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=float(timeout)) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"status": resp.status, "body": body, "headers": dict(resp.headers)}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8", errors="replace"), "error": str(e)}
    except Exception as e:
        return {"status": 0, "body": "", "error": str(e)}


def json_get(url, **kw):
    """HTTP GET + parse JSON. Requiere capability `network.http`.

    AUD-075: valida esquema de la URL (solo http/https).
    """
    require("network.http", op_desc=f"http.json_get({url!r})")
    r = get(url, **kw)
    try:
        r["json"] = _json.loads(r.get("body") or "null")
    except Exception:
        r["json"] = None
    return r
