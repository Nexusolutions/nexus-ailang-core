"""Manifiesto de proyecto AILang (ailang.project.json)."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List


DEFAULT = {
    "name": "app",
    "version": "0.1.0",
    "entry": "main.ailang",
    "src": ["."],
    "strict": False,
    "vm": False,
}


def load_project(root: str = ".") -> Dict[str, Any]:
    p = Path(root) / "ailang.project.json"
    if not p.exists():
        return dict(DEFAULT)
    data = json.loads(p.read_text(encoding="utf-8"))
    out = dict(DEFAULT)
    out.update(data)
    return out


def init_project(root: str = ".", name: str = "app") -> Path:
    root_p = Path(root)
    root_p.mkdir(parents=True, exist_ok=True)
    manifest = dict(DEFAULT, name=name)
    path = root_p / "ailang.project.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    main = root_p / manifest["entry"]
    if not main.exists():
        main.write_text(f'// {name}\nprint("hello", "{name}")\n', encoding="utf-8")
    return path


def run_project(root: str = ".") -> Any:
    from ailang.lang.interpreter import run_source
    cfg = load_project(root)
    entry = Path(root) / cfg["entry"]
    return run_source(
        entry.read_text(encoding="utf-8"),
        use_vm=bool(cfg.get("vm")),
        typecheck_strict=True if cfg.get("strict") else None,
    )
