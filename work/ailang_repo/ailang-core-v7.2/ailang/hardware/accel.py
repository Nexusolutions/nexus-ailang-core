"""Stubs GPU / NPU / TPU — detectan disponibilidad y delegan a CPU si no hay driver."""
from __future__ import annotations

from typing import Any, Sequence

from ailang.hardware.base import HardwareBackend, DeviceKind, TensorRef
from ailang.hardware.cpu import CPUBackend


class _AccelStub(HardwareBackend):
    kind: DeviceKind
    _probe_modules: tuple

    def __init__(self):
        self._cpu = CPUBackend()
        self._ok = False
        for mod in self._probe_modules:
            try:
                __import__(mod)
                self._ok = True
                break
            except ImportError:
                continue

    def available(self) -> bool:
        return self._ok

    def to_device(self, array: Any) -> TensorRef:
        # Sin driver real: CPU fallback transparente
        ref = self._cpu.to_device(array)
        return TensorRef(ref.data, ref.shape, ref.dtype, self.kind)

    def to_host(self, ref: TensorRef) -> Any:
        return self._cpu.to_host(ref)

    def matmul(self, a: TensorRef, b: TensorRef) -> TensorRef:
        return self._cpu.matmul(a, b)

    def vector_score(self, query: Sequence[float], docs: Sequence[Sequence[float]]) -> Sequence[float]:
        return self._cpu.vector_score(query, docs)


class GPUBackend(_AccelStub):
    kind = DeviceKind.GPU
    _probe_modules = ("cupy", "torch", "cuda")


class NPUBackend(_AccelStub):
    kind = DeviceKind.NPU
    _probe_modules = ("torch_npu", "openvino")


class TPUBackend(_AccelStub):
    kind = DeviceKind.TPU
    _probe_modules = ("torch_xla", "jax")


def select_backend(prefer: str = "cpu") -> HardwareBackend:
    order = {
        "gpu": (GPUBackend, CPUBackend),
        "npu": (NPUBackend, CPUBackend),
        "tpu": (TPUBackend, CPUBackend),
        "cpu": (CPUBackend,),
    }.get(prefer.lower(), (CPUBackend,))
    for cls in order:
        b = cls()
        if b.available():
            return b
    return CPUBackend()
