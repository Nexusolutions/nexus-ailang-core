"""ailang.playground.server — Backend para el playground web (Y2).

Sirve el HTML estático del playground y expone una API REST para
ejecutar código AILang desde el navegador.

Endpoints:
  GET  /           → playground/index.html
  POST /api/run     → ejecuta source AILang, retorna {stdout, stderr, result, error}
  POST /api/format  → formatea source, retorna {formatted}
  GET  /api/health  → health check

Uso:
  python -m ailang --serve
  # Abre http://localhost:8080
"""
from __future__ import annotations

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
from io import StringIO

from ailang.versions import __version__


PLAYGROUND_DIR = Path(__file__).resolve().parents[2] / "playground"


class PlaygroundHandler(BaseHTTPRequestHandler):
    """HTTP handler para el playground."""

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/" or path == "/index.html":
            self._serve_file(PLAYGROUND_DIR / "index.html", "text/html")
        elif path == "/api/health":
            self._json_response({"status": "ok", "version": __version__})
        elif path.startswith("/docs/"):
            doc_name = path.split("/docs/")[-1]
            doc_path = PLAYGROUND_DIR.parent / "docs" / doc_name
            if doc_path.exists():
                self._serve_file(doc_path, "text/markdown")
            else:
                self._not_found()
        else:
            self._not_found()

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/api/run":
            self._handle_run()
        elif path == "/api/format":
            self._handle_format()
        else:
            self._not_found()

    def _handle_run(self):
        body = self._read_body()
        if not body:
            self._json_response({"error": "empty body"}, 400)
            return

        try:
            data = json.loads(body)
            source = data.get("source", "")
            backend = data.get("backend", "vm")

            # Capture stdout/stderr
            old_stdout, old_stderr = sys.stdout, sys.stderr
            stdout_buf, stderr_buf = StringIO(), StringIO()
            sys.stdout, sys.stderr = stdout_buf, stderr_buf

            result = None
            error = None

            try:
                if backend == "air":
                    from ailang.runtime.air_interpreter import run_air
                    result = run_air(source, use_vm=True)
                elif backend == "vm":
                    from ailang.lang.vm import run_vm
                    result = run_vm(source)
                else:
                    from ailang.lang.interpreter import run_source
                    result = run_source(source)
            except Exception as e:
                error = str(e)
            finally:
                sys.stdout, sys.stderr = old_stdout, old_stderr

            response = {
                "stdout": stdout_buf.getvalue(),
                "stderr": stderr_buf.getvalue(),
                "result": self._serialize(result),
                "error": error,
            }
            self._json_response(response)

        except json.JSONDecodeError:
            self._json_response({"error": "invalid JSON"}, 400)

    def _handle_format(self):
        body = self._read_body()
        if not body:
            self._json_response({"error": "empty body"}, 400)
            return

        try:
            data = json.loads(body)
            source = data.get("source", "")

            from ailang.fmt import format_ast
            formatted = format_ast(source)
            self._json_response({"formatted": formatted})
        except Exception as e:
            self._json_response({"error": str(e)}, 500)

    def _serialize(self, value):
        """Serializa un valor AILang a JSON-compatible."""
        if value is None:
            return None
        if isinstance(value, (int, float, str, bool)):
            return value
        if isinstance(value, list):
            return [self._serialize(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._serialize(v) for k, v in value.items()}
        if hasattr(value, "tolist"):
            return value.tolist()
        if hasattr(value, "data") and hasattr(value.data, "tolist"):
            return value.data.tolist()
        return str(value)

    def _read_body(self) -> str:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return ""
        return self.rfile.read(length).decode("utf-8")

    def _serve_file(self, path: Path, content_type: str):
        if path.exists():
            content = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self._not_found()

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self):
        self.send_response(404)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        pass  # suppress logs


def serve(port: int = 8080):
    """Inicia el servidor del playground."""
    server = HTTPServer(("0.0.0.0", port), PlaygroundHandler)
    print(f"⚡ AILang Playground v{__version__}")
    print(f"   Open http://localhost:{port}")
    print(f"   Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n   Shutting down...")
        server.shutdown()
