"""Package manager de AILang (S5 — P2-7).

FASE 20 del prompt maestro. Soporta:
- init, install (local), list, run (existentes)
- publish: empaqueta + firma + sube a registry local
- update: actualiza un paquete desde el registry
- remove: desinstala un paquete
- search: busca paquetes en el registry
- checksum verification: verifica SHA-256 al instalar
- package signing: firma opcional Ed25519 del .ailpkg

Estructura de paquete:
  mypkg/
    ailang.json   {"name": "mypkg", "version": "0.1.0", "entry": "main.ailang"}
    main.ailang

Registry local: ~/.ailang/packages/
  index.json     — catálogo de paquetes instalados
  registry/      — paquetes publicados localmente (.ailpkg files)

Formato .ailpkg (tar.gz):
  manifest.json  — metadata del paquete
  main.ailang    — entry point
  [otros .py/.ailang]
  checksum.sha256 — SHA-256 de cada archivo
  signature.bin  — firma Ed25519 opcional (si se publicó con --sign)
"""
from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REGISTRY = Path.home() / ".ailang" / "packages"
REGISTRY_INDEX = REGISTRY / "index.json"
REMOTE_REGISTRY = REGISTRY / "registry"  # paquetes .ailpkg publicados localmente


def _ensure_registry() -> None:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    REMOTE_REGISTRY.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_INDEX.exists():
        REGISTRY_INDEX.write_text("{}", encoding="utf-8")


def _load_index() -> Dict[str, Any]:
    _ensure_registry()
    return json.loads(REGISTRY_INDEX.read_text(encoding="utf-8"))


def _save_index(idx: Dict[str, Any]) -> None:
    _ensure_registry()
    REGISTRY_INDEX.write_text(json.dumps(idx, indent=2), encoding="utf-8")


def _compute_checksum(data: bytes) -> str:
    """Retorna SHA-256 hex de los datos."""
    return hashlib.sha256(data).hexdigest()


def _compute_file_checksum(path: Path) -> str:
    """Retorna SHA-256 hex de un archivo."""
    return _compute_checksum(path.read_bytes())


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


def install_package(path: str, *, verify_checksum: bool = True) -> Dict[str, Any]:
    """Instala un paquete desde un directorio local o un .ailpkg."""
    src = Path(path).resolve()
    if src.is_file() and src.suffix == ".ailpkg":
        return _install_from_ailpkg(src, verify_checksum=verify_checksum)
    return _install_from_dir(src, verify_checksum=verify_checksum)


def _install_from_dir(src: Path, *, verify_checksum: bool = True) -> Dict[str, Any]:
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


def _install_from_ailpkg(pkg_path: Path, *, verify_checksum: bool = True) -> Dict[str, Any]:
    """Instala desde un archivo .ailpkg (tar.gz).

    Verifica checksums de cada archivo dentro del paquete antes de instalar.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        with tarfile.open(pkg_path, "r:gz") as tar:
            tar.extractall(tmp)

        # Verificar checksums
        checksum_file = tmp / "checksum.sha256"
        if verify_checksum and checksum_file.exists():
            expected = json.loads(checksum_file.read_text(encoding="utf-8"))
            for rel_path, expected_hash in expected.items():
                f = tmp / rel_path
                if not f.exists():
                    raise RuntimeError(f"archivo faltante en paquete: {rel_path}")
                actual = _compute_file_checksum(f)
                if actual != expected_hash:
                    raise RuntimeError(
                        f"checksum mismatch para {rel_path}: "
                        f"expected {expected_hash}, got {actual}"
                    )

        # Cargar manifest
        manifest = json.loads((tmp / "manifest.json").read_text(encoding="utf-8"))
        name = manifest["name"]
        dest = REGISTRY / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        # Copiar archivos del paquete (excluyendo metadata)
        for f in tmp.iterdir():
            if f.name in ("manifest.json", "checksum.sha256", "signature.bin"):
                continue
            if f.is_file():
                shutil.copy2(f, dest / f.name)
            elif f.is_dir():
                shutil.copytree(f, dest / f.name)

        idx = _load_index()
        idx[name] = {
            "version": manifest.get("version", "0.0.0"),
            "path": str(dest),
            "entry": manifest.get("entry", "main.ailang"),
            "source": str(pkg_path),
            "checksum_verified": verify_checksum,
        }
        _save_index(idx)
        return idx[name]


def publish_package(
    path: str,
    *,
    sign: bool = False,
    private_key: Any = None,
) -> Dict[str, Any]:
    """Publica un paquete al registry local (crea .ailpkg en REMOTE_REGISTRY).

    Args:
        path: directorio del paquete (con ailang.json)
        sign: si True, firma el paquete con Ed25519
        private_key: Ed25519PrivateKey para firmar

    Returns:
        Dict con info del paquete publicado
    """
    src = Path(path).resolve()
    manifest_path = src / "ailang.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no ailang.json in {src}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest["name"]
    version = manifest.get("version", "0.0.0")

    # Crear .ailpkg en temp dir
    with tempfile.NamedTemporaryFile(suffix=".ailpkg", delete=False) as tmp:
        pkg_path = Path(tmp.name)

    checksums: Dict[str, str] = {}
    with tarfile.open(pkg_path, "w:gz") as tar:
        # manifest.json
        manifest_data = json.dumps(manifest, indent=2).encode("utf-8")
        manifest_file = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        manifest_file.write(manifest_data)
        manifest_file.close()
        tar.add(manifest_file.name, arcname="manifest.json")
        checksums["manifest.json"] = _compute_checksum(manifest_data)
        Path(manifest_file.name).unlink()

        # Archivos del paquete
        for f in sorted(src.iterdir()):
            if f.name == "ailang.json":
                continue
            if f.is_file():
                tar.add(str(f), arcname=f.name)
                checksums[f.name] = _compute_file_checksum(f)
            elif f.is_dir():
                tar.add(str(f), arcname=f.name)
                for sub in f.rglob("*"):
                    if sub.is_file():
                        rel = str(sub.relative_to(src))
                        checksums[rel] = _compute_file_checksum(sub)

        # checksum.sha256
        checksum_data = json.dumps(checksums, indent=2, sort_keys=True).encode("utf-8")
        cs_file = tempfile.NamedTemporaryFile(suffix=".sha256", delete=False)
        cs_file.write(checksum_data)
        cs_file.close()
        tar.add(cs_file.name, arcname="checksum.sha256")
        Path(cs_file.name).unlink()

        # signature (opcional)
        if sign and private_key is not None:
            from ailang.cognitive import sign_bytecode  # facade to ailang_core
            signature = sign_bytecode(checksum_data, private_key)
            sig_file = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
            sig_file.write(signature)
            sig_file.close()
            tar.add(sig_file.name, arcname="signature.bin")
            Path(sig_file.name).unlink()

    # Mover al registry remoto
    _ensure_registry()
    dest_pkg = REMOTE_REGISTRY / f"{name}-{version}.ailpkg"
    shutil.move(str(pkg_path), str(dest_pkg))

    # Actualizar índice de registry
    idx = _load_index()
    if "published" not in idx:
        idx["published"] = {}
    idx["published"][f"{name}-{version}"] = {
        "name": name,
        "version": version,
        "path": str(dest_pkg),
        "signed": sign,
        "checksums": len(checksums),
    }
    _save_index(idx)

    return {
        "name": name,
        "version": version,
        "package": str(dest_pkg),
        "signed": sign,
        "files": len(checksums),
    }


def update_package(name: str, *, version: Optional[str] = None) -> Dict[str, Any]:
    """Actualiza un paquete desde el registry remoto al local."""
    idx = _load_index()
    published = idx.get("published", {})
    # Buscar versión más reciente o la especificada
    candidates = [
        (k, v) for k, v in published.items()
        if k.startswith(f"{name}-")
    ]
    if version:
        candidates = [(k, v) for k, v in candidates if v["version"] == version]
    if not candidates:
        raise KeyError(f"no hay paquete publicado: {name}" + (f"@{version}" if version else ""))
    # Tomar la más reciente (última en la lista)
    _, info = candidates[-1]
    return _install_from_ailpkg(Path(info["path"]))


def remove_package(name: str) -> Dict[str, Any]:
    """Desinstala un paquete del registry local."""
    idx = _load_index()
    if name not in idx or name == "published":
        raise KeyError(f"paquete no instalado: {name}")
    info = idx[name]
    dest = Path(info["path"])
    if dest.exists():
        shutil.rmtree(dest)
    del idx[name]
    _save_index(idx)
    return {"removed": name, "was_version": info.get("version", "unknown")}


def search_packages(query: str) -> List[Dict[str, Any]]:
    """Busca paquetes en el registry local por nombre."""
    idx = _load_index()
    results = []
    query_lower = query.lower()
    # Buscar en paquetes instalados
    for name, info in idx.items():
        if name == "published":
            continue
        if query_lower in name.lower():
            results.append({"name": name, "version": info.get("version"), "installed": True})
    # Buscar en paquetes publicados
    for key, info in idx.get("published", {}).items():
        if query_lower in info["name"].lower():
            results.append({
                "name": info["name"],
                "version": info["version"],
                "installed": info["name"] in idx,
                "signed": info.get("signed", False),
            })
    return results


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
    p_inst.add_argument("--no-verify", action="store_true", help="Skip checksum verification")
    sub.add_parser("list")
    p_run = sub.add_parser("run")
    p_run.add_argument("name")
    p_run.add_argument("--vm", action="store_true")
    p_pub = sub.add_parser("publish")
    p_pub.add_argument("path")
    p_pub.add_argument("--sign", action="store_true", help="Sign package with Ed25519")
    p_upd = sub.add_parser("update")
    p_upd.add_argument("name")
    p_upd.add_argument("--version", default=None)
    p_rm = sub.add_parser("remove")
    p_rm.add_argument("name")
    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    args = p.parse_args(argv)

    if args.cmd == "init":
        root = init_package(args.name, args.dest)
        print(f"created {root}")
        return 0
    if args.cmd == "install":
        info = install_package(args.path, verify_checksum=not args.no_verify)
        print(json.dumps(info, indent=2, default=str))
        return 0
    if args.cmd == "list":
        print(json.dumps(list_packages(), indent=2, default=str))
        return 0
    if args.cmd == "run":
        r = run_package(args.name, use_vm=args.vm)
        if r is not None:
            print(repr(r))
        return 0
    if args.cmd == "publish":
        info = publish_package(args.path, sign=args.sign)
        print(json.dumps(info, indent=2, default=str))
        return 0
    if args.cmd == "update":
        info = update_package(args.name, version=args.version)
        print(json.dumps(info, indent=2, default=str))
        return 0
    if args.cmd == "remove":
        info = remove_package(args.name)
        print(json.dumps(info, indent=2, default=str))
        return 0
    if args.cmd == "search":
        results = search_packages(args.query)
        print(json.dumps(results, indent=2, default=str))
        return 0
    p.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
