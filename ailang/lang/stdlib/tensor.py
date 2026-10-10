"""Stdlib `tensor` — Tensor type con NumPy + autograd (T3 — FASE 33).

FASE 33 del prompt maestro. Implementa un tipo Tensor profesional
basado en NumPy con:
- dtype, shape, device (CPU only por ahora)
- operaciones: matmul, softmax, normalize, add, mul, transpose
- autograd: gradient tape + backward pass
- capability enforcement: requiere `hardware.gpu` (CPU fallback)

No inventamos algoritmos — usamos NumPy (auditado, estable).
GPU/NPU/TPU reales son P4 (experimental).
"""
from __future__ import annotations

from typing import Any, List, Optional, Tuple, Union

import numpy as np

from ailang.runtime.capabilities import require


class Tensor:
    """Tensor multidimensional con soporte de autograd.

    Attributes:
        data: np.ndarray con los valores
        requires_grad: si True, acumula gradientes durante backward()
        grad: gradiente acumulado (None si requires_grad=False)
        _grad_fn: función de backward (para autograd)
        _parents: tensores de los que depende (para backprop)
    """

    def __init__(
        self,
        data: Union[np.ndarray, List, "Tensor", float, int],
        *,
        requires_grad: bool = False,
        dtype: Optional[str] = None,
    ):
        if isinstance(data, Tensor):
            self.data = data.data.copy()
        elif isinstance(data, np.ndarray):
            self.data = data.copy()
        else:
            self.data = np.array(data, dtype=dtype or np.float32)
        if dtype and isinstance(self.data, np.ndarray):
            self.data = self.data.astype(dtype)
        self.requires_grad = requires_grad
        self.grad: Optional[np.ndarray] = None
        self._grad_fn: Optional[callable] = None
        self._parents: List["Tensor"] = []

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.data.shape

    @property
    def dtype(self) -> str:
        return str(self.data.dtype)

    @property
    def ndim(self) -> int:
        return self.data.ndim

    @property
    def size(self) -> int:
        return self.data.size

    def __repr__(self) -> str:
        return f"Tensor(shape={self.shape}, dtype={self.dtype}, requires_grad={self.requires_grad})"

    def __str__(self) -> str:
        return f"Tensor({self.data})"

    # --- Operaciones con autograd ---

    def _ensure_tensor(self, other) -> "Tensor":
        if isinstance(other, Tensor):
            return other
        return Tensor(other)

    def _check_grad(self, other: "Tensor") -> bool:
        return self.requires_grad or other.requires_grad

    def add(self, other: Union["Tensor", float, int]) -> "Tensor":
        """Element-wise addition. Broadcast igual que NumPy."""
        require("hardware.gpu", op_desc="tensor.add()")
        other = self._ensure_tensor(other)
        out_data = self.data + other.data
        req_grad = self._check_grad(other)
        out = Tensor(out_data, requires_grad=req_grad)

        if req_grad:
            def _backward(grad):
                # grad tiene la shape del output; sumar para broadcast
                if self.requires_grad:
                    g = grad
                    while g.ndim > self.data.ndim:
                        g = g.sum(axis=0)
                    for i in range(g.ndim):
                        if g.shape[i] != self.data.shape[i] and self.data.shape[i] == 1:
                            g = g.sum(axis=i, keepdims=True)
                    self._accumulate_grad(g)
                if other.requires_grad:
                    g = grad
                    while g.ndim > other.data.ndim:
                        g = g.sum(axis=0)
                    for i in range(g.ndim):
                        if g.shape[i] != other.data.shape[i] and other.data.shape[i] == 1:
                            g = g.sum(axis=i, keepdims=True)
                    other._accumulate_grad(g)

            out._grad_fn = _backward
            out._parents = [self, other]
        return out

    def mul(self, other: Union["Tensor", float, int]) -> "Tensor":
        """Element-wise multiplication."""
        require("hardware.gpu", op_desc="tensor.mul()")
        other = self._ensure_tensor(other)
        out_data = self.data * other.data
        req_grad = self._check_grad(other)
        out = Tensor(out_data, requires_grad=req_grad)

        if req_grad:
            def _backward(grad):
                if self.requires_grad:
                    self._accumulate_grad(grad * other.data)
                if other.requires_grad:
                    other._accumulate_grad(grad * self.data)

            out._grad_fn = _backward
            out._parents = [self, other]
        return out

    def matmul(self, other: "Tensor") -> "Tensor":
        """Matrix multiplication (dot product para 1D, matmul para 2D+)."""
        require("hardware.gpu", op_desc="tensor.matmul()")
        other = self._ensure_tensor(other)
        out_data = self.data @ other.data
        req_grad = self._check_grad(other)
        out = Tensor(out_data, requires_grad=req_grad)

        if req_grad:
            def _backward(grad):
                if self.requires_grad:
                    if self.data.ndim == 1 and other.data.ndim == 1:
                        # dot product: grad is scalar
                        self._accumulate_grad(grad * other.data)
                    else:
                        self._accumulate_grad(grad @ other.data.T)
                if other.requires_grad:
                    if self.data.ndim == 1 and other.data.ndim == 1:
                        other._accumulate_grad(grad * self.data)
                    else:
                        other._accumulate_grad(self.data.T @ grad)

            out._grad_fn = _backward
            out._parents = [self, other]
        return out

    def softmax(self, axis: int = -1) -> "Tensor":
        """Softmax a lo largo de un axis."""
        require("hardware.gpu", op_desc="tensor.softmax()")
        shifted = self.data - np.max(self.data, axis=axis, keepdims=True)
        exp = np.exp(shifted)
        probs = exp / np.sum(exp, axis=axis, keepdims=True)
        out = Tensor(probs, requires_grad=self.requires_grad)

        if self.requires_grad:
            def _backward(grad):
                # d(softmax)/dx = softmax * (grad - sum(grad * softmax))
                s = probs
                dot = np.sum(grad * s, axis=axis, keepdims=True)
                self._accumulate_grad(s * (grad - dot))

            out._grad_fn = _backward
            out._parents = [self]
        return out

    def relu(self) -> "Tensor":
        """ReLU activation."""
        require("hardware.gpu", op_desc="tensor.relu()")
        out_data = np.maximum(0, self.data)
        out = Tensor(out_data, requires_grad=self.requires_grad)

        if self.requires_grad:
            def _backward(grad):
                self._accumulate_grad(grad * (self.data > 0).astype(grad.dtype))

            out._grad_fn = _backward
            out._parents = [self]
        return out

    def sum(self, axis=None, keepdims=False) -> "Tensor":
        """Suma todos los elementos o a lo largo de un axis."""
        require("hardware.gpu", op_desc="tensor.sum()")
        out_data = np.sum(self.data, axis=axis, keepdims=keepdims)
        out = Tensor(out_data, requires_grad=self.requires_grad)

        if self.requires_grad:
            def _backward(grad):
                if axis is not None and not keepdims:
                    grad = np.expand_dims(grad, axis)
                # Broadcast grad to self.shape
                self._accumulate_grad(np.broadcast_to(grad, self.data.shape).copy())

            out._grad_fn = _backward
            out._parents = [self]
        return out

    def mean(self, axis=None, keepdims=False) -> "Tensor":
        """Media."""
        require("hardware.gpu", op_desc="tensor.mean()")
        out_data = np.mean(self.data, axis=axis, keepdims=keepdims)
        out = Tensor(out_data, requires_grad=self.requires_grad)
        if self.requires_grad:
            n = self.data.size / out_data.size if out_data.size > 0 else 1
            def _backward(grad):
                if axis is not None and not keepdims:
                    grad = np.expand_dims(grad, axis)
                self._accumulate_grad(np.broadcast_to(grad / n, self.data.shape).copy())
            out._grad_fn = _backward
            out._parents = [self]
        return out

    def transpose(self) -> "Tensor":
        """Transpuesta (2D)."""
        require("hardware.gpu", op_desc="tensor.transpose()")
        out_data = self.data.T
        out = Tensor(out_data, requires_grad=self.requires_grad)
        if self.requires_grad:
            def _backward(grad):
                self._accumulate_grad(grad.T)
            out._grad_fn = _backward
            out._parents = [self]
        return out

    # --- Autograd ---

    def _accumulate_grad(self, grad: np.ndarray) -> None:
        if self.grad is None:
            self.grad = np.zeros_like(self.data)
        if grad.shape != self.grad.shape:
            grad = np.broadcast_to(grad, self.grad.shape).copy()
        self.grad = self.grad + grad

    def backward(self, grad: Optional[Union[np.ndarray, "Tensor"]] = None) -> None:
        """Backward pass: propaga gradientes desde este tensor."""
        if not self.requires_grad:
            raise RuntimeError("backward() requiere requires_grad=True")
        if grad is None:
            grad = np.ones_like(self.data)
        elif isinstance(grad, Tensor):
            grad = grad.data
        self._accumulate_grad(grad)

        # Topological order: recopilar todos los nodos del grafo
        topo: List[Tensor] = []
        visited: set = set()

        def build_topo(node: Tensor):
            if id(node) in visited:
                return
            visited.add(id(node))
            for parent in node._parents:
                build_topo(parent)
            topo.append(node)

        build_topo(self)

        # Backward en orden reverso
        for node in reversed(topo):
            if node._grad_fn is not None and node.grad is not None:
                node._grad_fn(node.grad)

    def zero_grad(self) -> None:
        """Reset gradientes a zero."""
        self.grad = None

    # --- Utility ---

    def tolist(self) -> list:
        return self.data.tolist()

    def item(self) -> float:
        """Si el tensor tiene un solo elemento, retornarlo como escalar."""
        return float(self.data.item())

    def numpy(self) -> np.ndarray:
        return self.data.copy()


# --- API del módulo ---

def tensor(data, requires_grad=False, dtype=None) -> Tensor:
    """Constructor de Tensor. Positional args: data, requires_grad, dtype."""
    require("hardware.gpu", op_desc="tensor()")
    return Tensor(data, requires_grad=bool(requires_grad), dtype=dtype)


def zeros(shape, dtype="float32") -> Tensor:
    """Tensor de ceros."""
    require("hardware.gpu", op_desc="tensor.zeros()")
    return Tensor(np.zeros(shape, dtype=dtype))


def ones(shape, dtype="float32") -> Tensor:
    """Tensor de unos."""
    require("hardware.gpu", op_desc="tensor.ones()")
    return Tensor(np.ones(shape, dtype=dtype))


def randn(shape, dtype="float32") -> Tensor:
    """Tensor con valores aleatorios (normal estándar)."""
    require("hardware.gpu", op_desc="tensor.randn()")
    return Tensor(np.random.randn(*shape).astype(dtype))


def eye(n, dtype="float32") -> Tensor:
    """Matriz identidad."""
    require("hardware.gpu", op_desc="tensor.eye()")
    return Tensor(np.eye(n, dtype=dtype))


_exports = {
    "tensor": tensor, "Tensor": Tensor,
    "zeros": zeros, "ones": ones, "randn": randn, "eye": eye,
}
