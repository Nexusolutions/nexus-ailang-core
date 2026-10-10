import random as _r

def seed(n):
    _r.seed(n)
    return None

def random():
    return _r.random()

def randint(a, b):
    return _r.randint(int(a), int(b))

def choice(xs):
    return _r.choice(list(xs))

def shuffle(xs):
    lst = list(xs)
    _r.shuffle(lst)
    return lst

def sample(xs, k):
    return _r.sample(list(xs), int(k))
