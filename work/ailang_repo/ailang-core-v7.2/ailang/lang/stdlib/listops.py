from functools import reduce as _reduce

def map_(fn, xs):
    return [fn(x) for x in xs]

def filter_(fn, xs):
    return [x for x in xs if fn(x)]

def reduce_(fn, xs, initial=None):
    if initial is None:
        return _reduce(fn, xs)
    return _reduce(fn, xs, initial)

def sum_(xs):
    return sum(xs)

def sorted_(xs, reverse=False):
    return sorted(xs, reverse=bool(reverse))
