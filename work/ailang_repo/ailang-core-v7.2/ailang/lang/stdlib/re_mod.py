import re as _re

def search(pattern, text):
    m = _re.search(str(pattern), str(text))
    if not m:
        return null if False else None
    return {"match": m.group(0), "start": m.start(), "end": m.end(), "groups": list(m.groups())}

def match(pattern, text):
    m = _re.match(str(pattern), str(text))
    if not m:
        return None
    return {"match": m.group(0), "start": m.start(), "end": m.end(), "groups": list(m.groups())}

def findall(pattern, text):
    return _re.findall(str(pattern), str(text))

def sub(pattern, repl, text, count=0):
    return _re.sub(str(pattern), str(repl), str(text), count=int(count))

def split(pattern, text, maxsplit=0):
    return _re.split(str(pattern), str(text), maxsplit=int(maxsplit))
