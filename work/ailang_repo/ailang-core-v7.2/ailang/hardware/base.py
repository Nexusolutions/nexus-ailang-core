"""Hardware backend abstraction — CPU / GPU / NPU / TPU."""
from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional, Sequence, Tuple


class DeviceKind(str, enum.Enum):
    CPU = "cpu"
    GPU = "gpu"
    NPU = "npu"
    TPU = "tpu"


@dataclass
class TensorRef:
    data: Any
    shape: Tuple[int, ...]
    dtype: str
    device: DeviceKind


class HardwareBackend(ABC):
    kind: DeviceKind

    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def to_device(self, array: Any) -> TensorRef: ...

    @abstractmethod
    def to_host(self, ref: TensorRef) -> Any: ...

    @abstractmethod
    def matmul(self, a: TensorRef, b: TensorRef) -> TensorRef: ...

    @abstractmethod
    def vector_score(self, query: Sequence[float], docs: Sequence[Sequence[float]]) -> Sequence[float]:
        """Similitud coseno query vs docs."""
        ...
