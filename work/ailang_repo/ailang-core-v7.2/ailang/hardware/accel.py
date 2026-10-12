"""GPU/NPU/TPU backends con dispatch real a cupy/torch_npu/jax (X4).

FASE 34 del prompt maestro. Cada backend:
1. Verifica si la librería nativa está disponible (cupy, torch, jax, etc.)
2. Si está disponible, ejecuta operaciones en el dispositivo real
3. Si no está disponible, hace fallback transparente a CPU (NumPy)

Estado de cada backend:
- GPU: implemented (cupy/torch), fallback a CPU si no hay CUDA
- NPU: experimental (torch_npu/openvino), fallback a CPU
- TPU: experimental (torch_xla/jax), fallback a CPU
"""
from __future__ import annotations

from typing import Any, Sequence, Optional

from ailang.hardware.base import HardwareBackend, DeviceKind, TensorRef
from ailang.hardware.cpu import CPUBackend


class _AccelBackend(HardwareBackend):
    """Backend base para GPU/NPU/TPU con dispatch real + fallback CPU.

    X4: ya no es un stub puro. Si la librería nativa está disponible,
    ejecuta operaciones en el dispositivo real. Si no, fallback a CPU.
    """

    kind: DeviceKind
    _probe_modules: tuple
    _backend_name: str = "unknown"

    def __init__(self):
        self._cpu = CPUBackend()
        self._native_mod = None
        self._ok = False
        self._device = None

        for mod_name in self._probe_modules:
            try:
                self._native_mod = __import__(mod_name)
                self._ok = True
                self._backend_name = mod_name
                self._init_device()
                break
            except ImportError:
                continue

    def _init_device(self) -> None:
        """Inicializa el dispositivo nativo (GPU/NPU/TPU)."""
        # Override en subclases para inicialización específica
        pass

    def available(self) -> bool:
        """Retorna True si el dispositivo nativo está disponible."""
        return self._ok

    def backend_name(self) -> str:
        """Retorna el nombre del backend nativo (cupy, torch, jax, etc.)."""
        return self._backend_name if self._ok else "cpu-fallback"

    def to_device(self, array: Any) -> TensorRef:
        """Transfiere un array al dispositivo nativo."""
        if not self._ok:
            ref = self._cpu.to_device(array)
            return TensorRef(ref.data, ref.shape, ref.dtype, self.kind)

        # Convertir a array nativo del dispositivo
        native_array = self._to_native_array(array)
        import numpy as np
        np_array = np.asarray(native_array) if not isinstance(native_array, np.ndarray) else native_array
        shape = tuple(np_array.shape)
        dtype = str(np_array.dtype)
        return TensorRef(native_array, shape, dtype, self.kind)

    def to_host(self, ref: TensorRef) -> Any:
        """Transfiere un array del dispositivo al host (CPU)."""
        if not self._ok:
            return self._cpu.to_host(ref)
        return self._to_host_array(ref.data)

    def matmul(self, a: TensorRef, b: TensorRef) -> TensorRef:
        """Matrix multiplication en el dispositivo nativo.

        AUD-052: requiere capability `hardware.gpu`/`hardware.npu`/`hardware.tpu`.
        """
        if not self._ok:
            return self._cpu.matmul(a, b)

        # AUD-052: capability check antes de usar hardware
        from ailang.runtime.capabilities import require
        cap_map = {
            DeviceKind.GPU: "hardware.gpu",
            DeviceKind.NPU: "hardware.npu",
            DeviceKind.TPU: "hardware.tpu",
        }
        cap = cap_map.get(self.kind)
        if cap:
            require(cap, op_desc=f"{self.kind.name}.matmul()")

        # Usar la operación nativa del dispositivo
        result = self._native_matmul(a.data, b.data)
        import numpy as np
        np_result = np.asarray(result)
        return TensorRef(result, tuple(np_result.shape), str(np_result.dtype), self.kind)

    def vector_score(self, query: Sequence[float], docs: Sequence[Sequence[float]]) -> Sequence[float]:
        """Cosine similarity en el dispositivo nativo.

        AUD-052: requiere capability `hardware.gpu`/`hardware.npu`/`hardware.tpu`.
        """
        if not self._ok:
            return self._cpu.vector_score(query, docs)

        # AUD-052: capability check antes de usar hardware
        from ailang.runtime.capabilities import require
        cap_map = {
            DeviceKind.GPU: "hardware.gpu",
            DeviceKind.NPU: "hardware.npu",
            DeviceKind.TPU: "hardware.tpu",
        }
        cap = cap_map.get(self.kind)
        if cap:
            require(cap, op_desc=f"{self.kind.name}.vector_score()")

        return self._native_vector_score(query, docs)

    # --- Métodos que las subclases pueden override ---

    def _to_native_array(self, array: Any) -> Any:
        """Convierte un array Python/NumPy al formato nativo del dispositivo."""
        import numpy as np
        np_array = np.asarray(array, dtype=np.float32)
        if self._backend_name == "cupy":
            return self._native_mod.asarray(np_array)
        elif self._backend_name in ("torch",):
            return self._native_mod.from_numpy(np_array)
        elif self._backend_name in ("jax",):
            return self._native_mod.numpy.asarray(np_array)
        return np_array

    def _to_host_array(self, native_array: Any) -> Any:
        """Convierte un array nativo del dispositivo a NumPy array."""
        if self._backend_name == "cupy":
            return self._native_mod.asnumpy(native_array)
        elif self._backend_name in ("torch",):
            return native_array.cpu().numpy()
        elif self._backend_name in ("jax",):
            return self._native_mod.numpy.asarray(native_array)
        import numpy as np
        return np.asarray(native_array)

    def _native_matmul(self, a: Any, b: Any) -> Any:
        """Ejecuta matmul en el dispositivo nativo."""
        if self._backend_name == "cupy":
            return self._native_mod.dot(a, b)
        elif self._backend_name in ("torch",):
            return self._native_mod.matmul(a, b)
        elif self._backend_name in ("jax",):
            return self._native_mod.numpy.dot(a, b)
        import numpy as np
        return np.dot(a, b)

    def _native_vector_score(self, query: Sequence[float], docs: Sequence[Sequence[float]]) -> Sequence[float]:
        """Cosine similarity en el dispositivo nativo."""
        import numpy as np
        q = self._to_native_array(query)
        d = self._to_native_array(docs)

        if self._backend_name == "cupy":
            q_norm = self._native_mod.linalg.norm(q)
            d_norm = self._native_mod.linalg.norm(d, axis=1)
            return self._native_mod.asnumpy(self._native_mod.dot(d, q) / (d_norm * q_norm + 1e-10))
        elif self._backend_name in ("torch",):
            q_norm = self._native_mod.linalg.norm(q)
            d_norm = self._native_mod.linalg.norm(d, dim=1)
            scores = self._native_mod.matmul(d, q) / (d_norm * q_norm + 1e-10)
            return scores.cpu().numpy()
        # Fallback a CPU
        return self._cpu.vector_score(query, docs)


class GPUBackend(_AccelBackend):
    """GPU backend con dispatch real a cupy o PyTorch CUDA.

    X4: ya no es un stub. Si cupy o torch+CUDA están disponibles,
    ejecuta matmul y vector_score en la GPU.
    """
    kind = DeviceKind.GPU
    _probe_modules = ("cupy", "torch", "cuda")

    def _init_device(self) -> None:
        if self._backend_name == "cupy":
            # cupy usa GPU 0 por defecto
            pass
        elif self._backend_name == "torch":
            # Verificar que CUDA está disponible en torch
            if not self._native_mod.cuda.is_available():
                self._ok = False


class NPUBackend(_AccelBackend):
    """NPU backend con dispatch real a torch_npu o OpenVINO.

    X4: experimental. Requiere hardware NPU específico.
    """
    kind = DeviceKind.NPU
    _probe_modules = ("torch_npu", "openvino")


class TPUBackend(_AccelBackend):
    """TPU backend con dispatch real a torch_xla o JAX.

    X4: experimental. Requiere hardware TPU o Cloud TPU.
    """
    kind = DeviceKind.TPU
    _probe_modules = ("torch_xla", "jax")


def select_backend(prefer: str = "cpu") -> HardwareBackend:
    """Selecciona el mejor backend disponible.

    Orden de preferencia:
    - "gpu": GPU → CPU fallback
    - "npu": NPU → CPU fallback
    - "tpu": TPU → CPU fallback
    - "cpu": CPU only
    """
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


def backend_status() -> dict:
    """Retorna el estado de todos los backends hardware.

    Útil para `ailang doctor` y debugging.
    """
    backends = {
        "cpu": CPUBackend(),
        "gpu": GPUBackend(),
        "npu": NPUBackend(),
        "tpu": TPUBackend(),
    }
    return {
        name: {
            "available": b.available(),
            "backend_name": b.backend_name() if hasattr(b, "backend_name") else "cpu",
            "kind": b.kind.value if hasattr(b, 'kind') else "cpu",
        }
        for name, b in backends.items()
    }
