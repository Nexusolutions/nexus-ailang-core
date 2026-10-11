"""Stdlib `quantum` — Tipos cuánticos con simulador statevector (Q2).

Incluye:
- Qubit, Circuit types
- Gates: H, X, Y, Z, CNOT, CZ, Rx, Ry, Rz
- StatevectorSimulator backend
- QAOA circuit builder para MaxCut
- Capability: quantum.execute
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ailang.runtime.capabilities import require


# --- Gates como matrices ---

def _hadamard() -> np.ndarray:
    return np.array([[1, 1], [1, -1]], dtype=complex) / math.sqrt(2)

def _pauli_x() -> np.ndarray:
    return np.array([[0, 1], [1, 0]], dtype=complex)

def _pauli_y() -> np.ndarray:
    return np.array([[0, -1j], [1j, 0]], dtype=complex)

def _pauli_z() -> np.ndarray:
    return np.array([[1, 0], [0, -1]], dtype=complex)

def _rx(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)

def _ry(theta: float) -> np.ndarray:
    c, s = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([[c, -s], [s, c]], dtype=complex)

def _rz(theta: float) -> np.ndarray:
    e1 = np.exp(-1j * theta / 2)
    e2 = np.exp(1j * theta / 2)
    return np.array([[e1, 0], [0, e2]], dtype=complex)

def _identity() -> np.ndarray:
    return np.eye(2, dtype=complex)

def _cnot() -> np.ndarray:
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 0, 1],
        [0, 0, 1, 0],
    ], dtype=complex)

def _cz() -> np.ndarray:
    return np.array([
        [1, 0, 0, 0],
        [0, 1, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, -1],
    ], dtype=complex)


GATES = {
    "H": _hadamard, "X": _pauli_x, "Y": _pauli_y, "Z": _pauli_z,
    "I": _identity,
}


class Circuit:
    """Circuito cuántico con n_qubits."""

    def __init__(self, n_qubits: int):
        if n_qubits < 1:
            raise ValueError("n_qubits debe ser >= 1")
        self.n_qubits = n_qubits
        self.gates: List[Tuple[str, List[int], Dict]] = []

    def h(self, q: int) -> "Circuit":
        """Hadamard gate en qubit q."""
        self._check(q)
        self.gates.append(("H", [q], {}))
        return self

    def x(self, q: int) -> "Circuit":
        self._check(q)
        self.gates.append(("X", [q], {}))
        return self

    def y(self, q: int) -> "Circuit":
        self._check(q)
        self.gates.append(("Y", [q], {}))
        return self

    def z(self, q: int) -> "Circuit":
        self._check(q)
        self.gates.append(("Z", [q], {}))
        return self

    def cnot(self, control: int, target: int) -> "Circuit":
        """CNOT gate: control → target."""
        self._check(control)
        self._check(target)
        if control == target:
            raise ValueError("control y target deben ser distintos")
        self.gates.append(("CNOT", [control, target], {}))
        return self

    def cz(self, control: int, target: int) -> "Circuit":
        self._check(control)
        self._check(target)
        self.gates.append(("CZ", [control, target], {}))
        return self

    def rx(self, q: int, theta: float) -> "Circuit":
        """Rotación Rx en qubit q."""
        self._check(q)
        self.gates.append(("RX", [q], {"theta": float(theta)}))
        return self

    def ry(self, q: int, theta: float) -> "Circuit":
        self._check(q)
        self.gates.append(("RY", [q], {"theta": float(theta)}))
        return self

    def rz(self, q: int, theta: float) -> "Circuit":
        self._check(q)
        self.gates.append(("RZ", [q], {"theta": float(theta)}))
        return self

    def _check(self, q: int) -> None:
        if not (0 <= q < self.n_qubits):
            raise ValueError(f"qubit {q} fuera de rango (0..{self.n_qubits - 1})")

    def __repr__(self) -> str:
        return f"Circuit(n_qubits={self.n_qubits}, gates={len(self.gates)})"

    def __str__(self) -> str:
        lines = [f"Circuit({self.n_qubits} qubits, {len(self.gates)} gates):"]
        for name, qubits, params in self.gates:
            q_str = ", ".join(str(q) for q in qubits)
            p_str = f"({params['theta']:.4f})" if "theta" in params else ""
            lines.append(f"  {name}{p_str} q[{q_str}]")
        return "\n".join(lines)


class StatevectorSimulator:
    """Simulador cuántico por statevector (exacto, no probabilístico)."""

    def __init__(self):
        self.name = "statevector"

    def run(self, circuit: Circuit, shots: int = 1024) -> Dict[str, Any]:
        """Ejecuta el circuito y retorna el statevector + mediciones."""
        require("quantum.execute", op_desc="quantum.simulate()")

        n = circuit.n_qubits
        dim = 2 ** n
        state = np.zeros(dim, dtype=complex)
        state[0] = 1.0  # |0...0>

        for name, qubits, params in circuit.gates:
            if name in ("H", "X", "Y", "Z", "I"):
                gate = GATES[name]()
                state = self._apply_single(state, gate, qubits[0], n)
            elif name == "RX":
                state = self._apply_single(state, _rx(params["theta"]), qubits[0], n)
            elif name == "RY":
                state = self._apply_single(state, _ry(params["theta"]), qubits[0], n)
            elif name == "RZ":
                state = self._apply_single(state, _rz(params["theta"]), qubits[0], n)
            elif name == "CNOT":
                state = self._apply_two(state, _cnot(), qubits[0], qubits[1], n)
            elif name == "CZ":
                state = self._apply_two(state, _cz(), qubits[0], qubits[1], n)

        # Probabilidades
        probs = np.abs(state) ** 2

        # Mediciones simuladas
        measurements = {}
        if shots > 0:
            rng = np.random.default_rng(42)
            for _ in range(shots):
                idx = rng.choice(dim, p=probs)
                bitstring = format(idx, f"0{n}b")
                measurements[bitstring] = measurements.get(bitstring, 0) + 1

        return {
            "statevector": state,
            "probabilities": probs,
            "measurements": measurements,
            "shots": shots,
            "n_qubits": n,
        }

    def _apply_single(self, state: np.ndarray, gate: np.ndarray, q: int, n: int) -> np.ndarray:
        """Aplica una gate de 1 qubit al qubit q del statevector."""
        new_state = state.copy()
        for i in range(len(state)):
            if (i >> q) & 1 == 0:
                j = i | (1 << q)
                a, b = state[i], state[j]
                new_state[i] = gate[0, 0] * a + gate[0, 1] * b
                new_state[j] = gate[1, 0] * a + gate[1, 1] * b
        return new_state

    def _apply_two(self, state: np.ndarray, gate: np.ndarray, q1: int, q2: int, n: int) -> np.ndarray:
        """Aplica una gate de 2 qubits."""
        new_state = state.copy()
        dim = len(state)
        for i in range(dim):
            b1 = (i >> q1) & 1
            b2 = (i >> q2) & 1
            idx = b1 * 2 + b2
            # Los 4 índices del subespacio
            indices = []
            for d1 in (0, 1):
                for d2 in (0, 1):
                    j = i
                    if d1:
                        j |= (1 << q1)
                    else:
                        j &= ~(1 << q1)
                    if d2:
                        j |= (1 << q2)
                    else:
                        j &= ~(1 << q2)
                    indices.append(j)
            vals = [state[idx2] for idx2 in indices]
            for row in range(4):
                new_state[indices[row]] = sum(gate[row, col] * vals[col] for col in range(4))
        return new_state


# --- QAOA para MaxCut ---

def qaoa_circuit(n_qubits: int, edges: List[Tuple[int, int, float]],
                 gamma: float, beta: float, p: int = 1) -> Circuit:
    """Construye un circuito QAOA para MaxCut.

    Args:
        n_qubits: número de qubits (= número de vértices del grafo)
        edges: lista de aristas (u, v, weight)
        gamma: parámetro de coste (ángulo del Hamiltoniano de coste)
        beta: parámetro de mezcla (ángulo del Hamiltoniano de mezcla)
        p: profundidad del QAOA (número de capas)

    Returns:
        Circuit listo para simular
    """
    require("quantum.execute", op_desc="quantum.qaoa_circuit()")

    c = Circuit(n_qubits)

    # Capa inicial: superposición uniforme
    for q in range(n_qubits):
        c.h(q)

    # p capas de QAOA
    for _ in range(p):
        # Hamiltoniano de coste: ZZ interactions para cada arista
        for u, v, w in edges:
            c.cnot(u, v)
            c.rz(v, 2 * gamma * w)
            c.cnot(u, v)

        # Hamiltoniano de mezcla: Rx en cada qubit
        for q in range(n_qubits):
            c.rx(q, 2 * beta)

    return c


def qaoa_maxcut(g, gamma: float = 0.5, beta: float = 0.5,
                p: int = 1, shots: int = 1024) -> Dict[str, Any]:
    """Ejecuta QAOA para MaxCut en un grafo.

    Args:
        g: objeto Graph
        gamma, beta: parámetros QAOA
        p: profundidad
        shots: número de mediciones

    Returns:
        Dict con best_cut, cut_value, measurements
    """
    require("quantum.execute", op_desc="quantum.qaoa_maxcut()")

    n = g.n
    edges = g.edges

    # Construir circuito QAOA
    c = qaoa_circuit(n, edges, gamma, beta, p)

    # Simular
    sim = StatevectorSimulator()
    result = sim.run(c, shots=shots)

    # Evaluar cada medición como un corte
    best_bits = None
    best_value = float("-inf")
    for bitstring, count in result["measurements"].items():
        bits = [int(b) for b in bitstring]
        value = g.cut_value(bits)
        if value > best_value:
            best_value = value
            best_bits = tuple(bits)

    # También evaluar el statevector directamente (max prob)
    probs = result["probabilities"]
    best_idx = np.argmax(probs)
    best_sv_bits = tuple(int(b) for b in format(best_idx, f"0{n}b"))
    sv_value = g.cut_value(best_sv_bits)
    if sv_value > best_value:
        best_value = sv_value
        best_bits = best_sv_bits

    return {
        "bits": best_bits,
        "cut_value": best_value,
        "method": "qaoa",
        "gamma": gamma,
        "beta": beta,
        "p": p,
        "shots": shots,
        "measurements": result["measurements"],
    }


# --- Export ---

_exports = {
    "Circuit": Circuit, "StatevectorSimulator": StatevectorSimulator,
    "qaoa_circuit": qaoa_circuit, "qaoa_maxcut": qaoa_maxcut,
}
