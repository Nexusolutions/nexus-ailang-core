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
    """Format template con placeholders posicionales {0}, {1}, ...

    AUD-071: NO usa str.format() de Python directamente porque permite
    acceso a atributos (`{0.__class__}`) que filtra info interna.
    En su lugar, usa string.Template (sustitución ${0}, ${1}) o
    reemplaza solo {N} con args[N] manualmente.
    """
    import re
    template_str = str(template)

    def _replacer(match):
        idx_str = match.group(1)
        try:
            idx = int(idx_str)
            if idx < len(args):
                return str(args[idx])
            return match.group(0)  # placeholder sin arg: dejar tal cual
        except (ValueError, IndexError):
            return match.group(0)

    # Solo {N} (número); NO {0.attr} ni {0[key]} — estos se dejan tal cual
    return re.sub(r"\{(\d+)\}", _replacer, template_str)
