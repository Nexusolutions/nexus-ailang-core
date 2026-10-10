from pathlib import Path

def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")

def write_text(path: str, content: str) -> None:
    Path(path).write_text(str(content), encoding="utf-8")
    return None

def exists(path: str) -> bool:
    return Path(path).exists()

def lines(path: str):
    return Path(path).read_text(encoding="utf-8").splitlines()
