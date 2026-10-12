"""ailang doctor — P2-15.

Diagnostica el estado de todos los componentes del proyecto AILang:
- runtime (interpreter, VM)
- compiler (frontend, AST)
- bytecode_io (carga/guarda .ailc)
- stdlib (módulos disponibles)
- database (SQLite)
- LSP (capabilities)
- debugger (pause real)
- backends hardware (CPU/GPU/NPU/TPU)
- dependencias (numpy, cryptography, psycopg)

Uso: `python -m ailang doctor`
"""
from __future__ import annotations

import importlib
import json
import sys
from typing import Any, Dict, List


def _check_component(name: str, check_fn) -> Dict[str, Any]:
    """Ejecuta check_fn y retorna {name, status, detail}."""
    try:
        result = check_fn()
        return {
            "component": name,
            "status": "ok" if result.get("ok", True) else "fail",
            "detail": result.get("detail", ""),
        }
    except Exception as e:
        return {"component": name, "status": "error", "detail": str(e)}


def _check_runtime() -> Dict[str, Any]:
    from ailang.lang.interpreter import run_source
    result = run_source("1 + 2")
    return {"ok": result == 3, "detail": f"interpreter: 1+2 = {result}"}


def _check_vm() -> Dict[str, Any]:
    from ailang.lang.vm import run_vm
    result = run_vm("1 + 2")
    return {"ok": result == 3, "detail": f"VM: 1+2 = {result}"}


def _check_compiler() -> Dict[str, Any]:
    from ailang.lang.parser import parse
    from ailang.lang import ast_nodes as A
    prog = parse("let x = 1\nfn f() { return x }")
    nodes = [type(s).__name__ for s in prog.body]
    return {"ok": "Let" in nodes and "Function" in nodes, "detail": f"AST nodes: {nodes}"}


def _check_bytecode_io() -> Dict[str, Any]:
    from ailang.lang.bytecode_io import save_bytecode, load_and_run
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".ailc", delete=False) as f:
        path = f.name
    try:
        save_bytecode("let x = 42\nx", path)
        result = load_and_run(path)
        return {"ok": result == 42, "detail": f"round-trip .ailc: result = {result}"}
    finally:
        if os.path.exists(path):
            os.unlink(path)


def _check_stdlib() -> Dict[str, Any]:
    from ailang.lang.stdlib import builtin_modules
    mods = builtin_modules()
    expected = {"math", "io", "json", "strings", "time", "sys", "re", "listops", "random", "path", "test"}
    missing = expected - set(mods.keys())
    return {"ok": not missing, "detail": f"stdlib: {len(mods)} modules, missing: {missing or 'none'}"}


def _check_database() -> Dict[str, Any]:
    from ailang.storage.sqlite_backend import SQLiteStorage
    from ailang.storage.base import DocumentRecord, ChunkRecord
    import inspect
    s = SQLiteStorage(":memory:")
    sig = inspect.signature(s.upsert_document)
    # Adaptarse al signature real: (record: DocumentRecord)
    if len(sig.parameters) == 1:
        s.upsert_document(DocumentRecord(
            id="d1", source="test", path="/p",
            content="hello world", doc_type="text", title="Doctor Test",
        ))
        s.replace_chunks("d1", [ChunkRecord(id="c1", document_id="d1", content="hello world", embedding=[0.1, 0.2])])
    else:
        s.upsert_document("d1", "test", "/p", "hello world", "text")
        s.replace_chunks("d1", [("c1", "hello world", [0.1, 0.2])])
    docs = s.list_documents()
    s.close()
    return {"ok": len(docs) >= 1, "detail": f"SQLite CRUD: 1 doc inserted, retrieved {len(docs)}"}


def _check_lsp() -> Dict[str, Any]:
    from ailang.lsp import AILangLanguageServer
    s = AILangLanguageServer()
    # Verificar que existen los métodos nuevos
    methods = ["_extract_symbols", "_extract_semantic_tokens", "_signature_help"]
    missing = [m for m in methods if not hasattr(s, m)]
    return {"ok": not missing, "detail": f"LSP methods: all present" if not missing else f"LSP missing: {missing}"}


def _check_debugger() -> Dict[str, Any]:
    from ailang.debugger import Debugger
    import threading
    src = "let x = 1\nlet y = 2"
    dbg = Debugger(src)
    dbg.set_breakpoint(1)
    t = threading.Thread(target=dbg.run, daemon=True)
    t.start()
    paused = dbg.wait_paused(timeout=2.0)
    if paused:
        dbg.continue_run()
    t.join(timeout=1.0)
    return {"ok": paused, "detail": f"debugger pause at bp: {'yes' if paused else 'no'}"}


def _check_hardware() -> Dict[str, Any]:
    from ailang.hardware.accel import select_backend, GPUBackend, NPUBackend, TPUBackend
    cpu = select_backend("cpu")
    gpu = GPUBackend()
    npu = NPUBackend()
    tpu = TPUBackend()
    return {
        "ok": cpu.available(),
        "detail": f"CPU={cpu.available()}, GPU={gpu.available()}, NPU={npu.available()}, TPU={tpu.available()}",
    }


def _check_cognitive() -> Dict[str, Any]:
    try:
        from ailang.cognitive import CognitiveBrainStore, CognitiveBrainEngine
        store = CognitiveBrainStore(":memory:", tenant_id="doctor")
        engine = CognitiveBrainEngine(store)
        engine.ingest("test", "/p", "hello world")
        results = engine.search("hello", top_k=1)
        store.close()
        return {"ok": len(results) > 0, "detail": f"brain: ingested 1 doc, search returned {len(results)}"}
    except ImportError as e:
        return {"ok": False, "detail": f"ailang_core not available: {e}"}


def _check_dependencies() -> Dict[str, Any]:
    deps = {}
    for mod_name in ("numpy", "cryptography", "psycopg"):
        try:
            m = importlib.import_module(mod_name)
            ver = getattr(m, "__version__", "unknown")
            deps[mod_name] = ver
        except ImportError:
            deps[mod_name] = None
    return {
        "ok": deps.get("numpy") is not None,
        "detail": f"numpy={deps.get('numpy')}, cryptography={deps.get('cryptography')}, psycopg={deps.get('psycopg')}",
    }


def run_doctor() -> int:
    """Ejecuta todos los checks e imprime un reporte. Retorna 0 si todo OK, 1 si hay fails."""
    print(f"=== AILang doctor ===")
    from ailang.versions import __version__, LANGUAGE_VERSION, RUNTIME_VERSION, BYTECODE_VERSION, IR_VERSION
    print(f"Package version:    {__version__}")
    print(f"Language version:   {LANGUAGE_VERSION}")
    print(f"Runtime version:    {RUNTIME_VERSION}")
    print(f"Bytecode version:   {BYTECODE_VERSION}")
    print(f"IR version:         {IR_VERSION}")
    print()

    checks = [
        ("runtime (interpreter)", _check_runtime),
        ("vm", _check_vm),
        ("compiler (frontend)", _check_compiler),
        ("bytecode_io (.ailc)", _check_bytecode_io),
        ("stdlib", _check_stdlib),
        ("database (SQLite)", _check_database),
        ("LSP server", _check_lsp),
        ("debugger (pause)", _check_debugger),
        ("hardware (backends)", _check_hardware),
        ("cognitive runtime", _check_cognitive),
        ("dependencies", _check_dependencies),
    ]

    results: List[Dict[str, Any]] = []
    for name, fn in checks:
        result = _check_component(name, fn)
        results.append(result)
        icon = "✅" if result["status"] == "ok" else ("❌" if result["status"] == "fail" else "⚠️")
        print(f"  {icon} {name:25s} {result['detail']}")

    print()
    ok_count = sum(1 for r in results if r["status"] == "ok")
    fail_count = sum(1 for r in results if r["status"] == "fail")
    err_count = sum(1 for r in results if r["status"] == "error")
    print(f"Summary: {ok_count} ok, {fail_count} fail, {err_count} error (total {len(results)})")

    if fail_count or err_count:
        print("\nFailures:")
        for r in results:
            if r["status"] != "ok":
                print(f"  - {r['component']}: {r['detail']}")
        return 1
    print("\nAll components OK.")
    return 0


if __name__ == "__main__":
    sys.exit(run_doctor())
