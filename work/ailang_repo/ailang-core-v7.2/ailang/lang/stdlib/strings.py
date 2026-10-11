def length(s):
    return len(str(s))

def upper(s):
    return str(s).upper()

def lower(s):
    return str(s).lower()

def strip(s):
    return str(s).strip()

def split(s, sep=None):
    return str(s).split(sep) if sep is not None else str(s).split()

def join(sep, xs):
    return str(sep).join(str(x) for x in xs)

def replace(s, old, new):
    return str(s).replace(str(old), str(new))

def startswith(s, prefix):
    return str(s).startswith(str(prefix))

def endswith(s, suffix):
    return str(s).endswith(str(suffix))

def contains(s, sub):
    return str(sub) in str(s)

def format(template, *args):
    return str(template).format(*args)
