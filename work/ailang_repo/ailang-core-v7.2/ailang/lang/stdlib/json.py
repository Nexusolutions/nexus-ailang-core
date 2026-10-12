import json as _json

def loads(s: str):
    return _json.loads(s)

def dumps(obj, indent=None) -> str:
    return _json.dumps(obj, indent=indent, ensure_ascii=False)
