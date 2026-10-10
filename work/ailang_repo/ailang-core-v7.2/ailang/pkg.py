"""Package manager local de AILang (Nivel B).

Estructura de paquete:
  mypkg/
    ailang.json   {"name": "mypkg", "version": "0.1.0", "entry": "main.ailang"}
    main.ailang

Comandos:
  python -m ailang pkg init [name]
  python -m ailang pkg install <path>
  python -m ailang pkg list
  python -m ailang pkg run <name>
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY = Path.home() / ".ailang" / "packages"
REGISTRY_INDEX = REGISTRY / "index.json"


def _ensure_registry() -> None:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_INDEX.exists():
        REGISTRY_INDEX.write_text("{}", encoding="utf-8")


def _load_index() -> Dict[str, Any]:
    _ensure_registry()
    return json.loads(REGISTRY_INDEX.read_text(encoding="utf-8"))


def _save_index(idx: Dict[str, Any]) -> None:
    _ensure_registry()
    REGISTRY_INDEX.write_text(json.dumps(idx, indent=2), encoding="utf-8")


def init_package(name: str = "mypkg", dest: Optional[str] = None) -> Path:
    root = Path(dest or name)
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "version": "0.1.0",
        "entry": "main.ailang",
        "dependencies": [],
    }
    (root / "ailang.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "main.ailang").write_text(
        f'// package {name}\nprint("hello from {name}")\n',
        encoding="utf-8",
    )
    return root


def install_package(path: str) -> Dict[str, Any]:
    src = Path(path).resolve()
    manifest_path = src / "ailang.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no ailang.json in {src}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest["name"]
    dest = REGISTRY / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    idx = _load_index()
    idx[name] = {
        "version": manifest.get("version", "0.0.0"),
        "path": str(dest),
        "entry": manifest.get("entry", "main.ailang"),
    }
    _save_index(idx)
    return idx[name]


def list_packages() -> Dict[str, Any]:
    return _load_index()


def run_package(name: str, *, use_vm: bool = False) -> Any:
    from ailang.lang.interpreter import run_source
    idx = _load_index()
    if name not in idx:
        raise KeyError(f"paquete no instalado: {name}")
    info = idx[name]
    entry = Path(info["path"]) / info["entry"]
    return run_source(entry.read_text(encoding="utf-8"), use_vm=use_vm)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="ailang pkg")
    sub = p.add_subparsers(dest="cmd")
    p_init = sub.add_parser("init")
    p_init.add_argument("name", nargs="?", default="mypkg")
    p_init.add_argument("--dest", default=None)
    p_inst = sub.add_parser("install")
    p_inst.add_argument("path")
    sub.add_parser("list")
    p_run = sub.add_parser("run")
    p_run.add_argument("name")
    p_run.add_argument("--vm", action="store_true")
    args = p.parse_args(argv)
    if args.cmd == "init":
        root = init_package(args.name, args.dest)
        print(f"created {root}")
        return 0
    if args.cmd == "install":
        info = install_package(args.path)
        print(json.dumps(info, indent=2))
        return 0
    if args.cmd == "list":
        print(json.dumps(list_packages(), indent=2))
        return 0
    if args.cmd == "run":
        r = run_package(args.name, use_vm=args.vm)
        if r is not None:
            print(repr(r))
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
