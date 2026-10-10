"""Backend CPU (NumPy) — siempre disponible."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np

from ailang.hardware.base import HardwareBackend, DeviceKind, TensorRef


class CPUBackend(HardwareBackend):
    kind = DeviceKind.CPU

    def available(self) -> bool:
        return True

    def to_device(self, array: Any) -> TensorRef:
        arr = np.asarray(array)
        return TensorRef(arr, tuple(arr.shape), str(arr.dtype), DeviceKind.CPU)

    def to_host(self, ref: TensorRef) -> Any:
        return np.asarray(ref.data)

    def matmul(self, a: TensorRef, b: TensorRef) -> TensorRef:
        out = np.matmul(np.asarray(a.data), np.asarray(b.data))
        return TensorRef(out, tuple(out.shape), str(out.dtype), DeviceKind.CPU)

    def vector_score(self, query: Sequence[float], docs: Sequence[Sequence[float]]) -> Sequence[float]:
        q = np.asarray(query, dtype=np.float64)
        qn = np.linalg.norm(q) + 1e-12
        scores = []
        for d in docs:
            v = np.asarray(d, dtype=np.float64)
            scores.append(float(np.dot(q, v) / (qn * (np.linalg.norm(v) + 1e-12))))
        return scores
