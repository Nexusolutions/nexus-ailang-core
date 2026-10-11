"""Stdlib `graph` — Tipo Graph nativo con algoritmos de optimización (Q1).

Incluye:
- Graph type con vertices, edges, weights
- Generación: random, complete, cycle, path
- Métricas: density, degree, connected_components
- MaxCut: exact, greedy, local_search, QAOA-ready
- Basado en el análisis de Nexus Ω / EVA-Ω v0.2
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ailang.runtime.capabilities import require


class Graph:
    """Grafo ponderado no dirigido."""

    def __init__(self, n: int, edges: List[Tuple[int, int, float]]):
        if n < 1:
            raise ValueError("n debe ser >= 1")
        self._n = n
        self._adj: Dict[int, List[Tuple[int, float]]] = {i: [] for i in range(n)}
        for u, v, w in edges:
            if not (0 <= u < n and 0 <= v < n) or u == v:
                raise ValueError(f"arista inválida: ({u}, {v})")
            if w < 0:
                raise ValueError("pesos deben ser no negativos")
            self._adj[u].append((v, float(w)))
            self._adj[v].append((u, float(w)))
        self._edges = [(u, v, float(w)) for u, v, w in edges]

    @property
    def n(self) -> int:
        return self._n

    @property
    def edges(self) -> List[Tuple[int, int, float]]:
        return list(self._edges)

    def vertices(self) -> List[int]:
        return list(range(self._n))

    def neighbors(self, u: int) -> List[Tuple[int, float]]:
        return list(self._adj.get(u, []))

    def weight(self, u: int, v: int) -> float:
        for nb, w in self._adj.get(u, []):
            if nb == v:
                return w
        return 0.0

    def degree(self, u: int) -> int:
        return len(self._adj.get(u, []))

    def density(self) -> float:
        max_edges = self._n * (self._n - 1) / 2
        return len(self._edges) / max_edges if max_edges > 0 else 0.0

    def connected_components(self) -> List[List[int]]:
        visited = set()
        components = []
        for start in range(self._n):
            if start in visited:
                continue
            comp = []
            stack = [start]
            while stack:
                u = stack.pop()
                if u in visited:
                    continue
                visited.add(u)
                comp.append(u)
                for v, _ in self._adj[u]:
                    if v not in visited:
                        stack.append(v)
            components.append(comp)
        return components

    def cut_value(self, bits: Sequence[int]) -> float:
        """Valor de un corte: suma de pesos de aristas entre particiones."""
        return sum(w for u, v, w in self._edges if bits[u] != bits[v])

    def __repr__(self) -> str:
        return f"Graph(n={self._n}, edges={len(self._edges)}, density={self.density():.2f})"


# --- Generación ---

def weighted(n: int, edges: List[Tuple[int, int, float]]) -> Graph:
    """Crea un grafo ponderado desde lista de aristas."""
    require("graph.compute", op_desc="graph.weighted()")
    return Graph(n, edges)


def random(n: int, p: float = 0.35, seed: int = 42, max_weight: int = 10) -> Graph:
    """Genera un grafo aleatorio de Erdős-Rényi con pesos."""
    require("graph.compute", op_desc="graph.random()")
    import random as _rng
    rng = _rng.Random(seed)
    edges = []
    for u in range(n):
        for v in range(u + 1, n):
            if rng.random() < p:
                edges.append((u, v, float(rng.randint(1, max_weight))))
    return Graph(n, edges)


def complete(n: int, weight: float = 1.0) -> Graph:
    """Crea un grafo completo K_n con peso uniforme."""
    require("graph.compute", op_desc="graph.complete()")
    edges = [(u, v, weight) for u in range(n) for v in range(u + 1, n)]
    return Graph(n, edges)


def cycle(n: int, weight: float = 1.0) -> Graph:
    """Crea un ciclo C_n."""
    require("graph.compute", op_desc="graph.cycle()")
    edges = [(i, (i + 1) % n, weight) for i in range(n)]
    return Graph(n, edges)


def path(n: int, weight: float = 1.0) -> Graph:
    """Crea un camino P_n."""
    require("graph.compute", op_desc="graph.path()")
    edges = [(i, i + 1, weight) for i in range(n - 1)]
    return Graph(n, edges)


# --- MaxCut ---

def maxcut_exact(g: Graph) -> Dict[str, Any]:
    """MaxCut por enumeración exacta. Solo para grafos pequeños (n <= 20)."""
    require("graph.compute", op_desc="graph.maxcut_exact()")
    from itertools import product
    n = g.n
    if n > 20:
        raise ValueError("maxcut_exact requiere n <= 20")
    best_bits, best = None, float("-inf")
    evals = 0
    for tail in product((0, 1), repeat=n - 1):
        bits = (0,) + tail
        val = g.cut_value(bits)
        evals += 1
        if val > best:
            best_bits, best = bits, val
    return {"bits": best_bits, "cut_value": best, "evaluations": evals, "method": "exact"}


def maxcut_greedy(g: Graph, order: Optional[List[int]] = None) -> Dict[str, Any]:
    """MaxCut greedy: asigna cada vértice al lado que maximiza el corte parcial."""
    require("graph.compute", op_desc="graph.maxcut_greedy()")
    n = g.n
    order = list(order) if order else list(range(n))
    assigned = set()
    bits = [0] * n
    evals = 0
    for v in order:
        s0 = s1 = 0.0
        for u, w in g.neighbors(v):
            if u in assigned:
                if bits[u] == 0:
                    s1 += w
                else:
                    s0 += w
        bits[v] = 1 if s1 > s0 else 0
        assigned.add(v)
        evals += 2
    return {"bits": tuple(bits), "cut_value": g.cut_value(bits), "evaluations": evals, "method": "greedy"}


def maxcut_local_search(g: Graph, initial: Optional[List[int]] = None, max_passes: int = 100) -> Dict[str, Any]:
    """MaxCut por búsqueda local: flip un bit a la vez hasta no mejorar."""
    require("graph.compute", op_desc="graph.maxcut_local_search()")
    n = g.n
    bits = list(initial) if initial else [0] * n
    current = g.cut_value(bits)
    evals = 1
    for _ in range(max_passes):
        improved = False
        for i in range(n):
            candidate = bits.copy()
            candidate[i] ^= 1
            value = g.cut_value(candidate)
            evals += 1
            if value > current + 1e-12:
                bits, current = candidate, value
                improved = True
        if not improved:
            break
    return {"bits": tuple(bits), "cut_value": current, "evaluations": evals, "method": "local_search"}


def maxcut_gap(result: Dict, optimal: float) -> float:
    """Calcula el gap relativo al óptimo."""
    return (optimal - result["cut_value"]) / max(optimal, 1e-12)


# --- Export ---

_exports = {
    "Graph": Graph,
    "weighted": weighted, "random": random, "complete": complete,
    "cycle": cycle, "path": path,
    "maxcut_exact": maxcut_exact, "maxcut_greedy": maxcut_greedy,
    "maxcut_local_search": maxcut_local_search, "maxcut_gap": maxcut_gap,
}
