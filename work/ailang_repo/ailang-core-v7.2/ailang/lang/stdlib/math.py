import math as _m

pi = _m.pi
e = _m.e

def abs_(x):
    return abs(x)

def min_(*a):
    return min(a) if len(a) > 1 else min(a[0])

def max_(*a):
    return max(a) if len(a) > 1 else max(a[0])

def sqrt_(x):
    return _m.sqrt(float(x))

def pow_(x, y):
    return float(x) ** float(y)

def floor_(x):
    return _m.floor(float(x))

def ceil_(x):
    return _m.ceil(float(x))
