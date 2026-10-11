"""Stdlib `selector` — Selector adaptativo genérico (Q3).

Generaliza el patrón de EVA-Ω: calibrar estrategias en un caso separado,
luego elegir dinámicamente basado en historial de pérdida.

Funciona para:
- Selección de algoritmo (greedy vs local_search vs qaoa)
- Selección de backend (interp vs vm vs llvm)
- Cualquier dominio donde haya múltiples estrategias con trade-offs
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ailang.runtime.capabilities import require


@dataclass
class StrategyStats:
    """Estadísticas acumuladas de una estrategia."""
    name: str
    observations: int = 0
    cumulative_loss: float = 0.0
    cumulative_quality: float = 0.0
    cumulative_cost: float = 0.0

    @property
    def mean_loss(self) -> float:
        return self.cumulative_loss / self.observations if self.observations > 0 else float("inf")

    @property
    def mean_quality(self) -> float:
        return self.cumulative_quality / self.observations if self.observations > 0 else 0.0

    @property
    def mean_cost(self) -> float:
        return self.cumulative_cost / self.observations if self.observations > 0 else 0.0

    def update(self, loss: float, quality: float, cost: float) -> None:
        self.observations += 1
        self.cumulative_loss += loss
        self.cumulative_quality += quality
        self.cumulative_cost += cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "observations": self.observations,
            "mean_loss": round(self.mean_loss, 6),
            "mean_quality": round(self.mean_quality, 6),
            "mean_cost": round(self.mean_cost, 6),
        }


class AdaptiveSelector:
    """Selector adaptativo que elige la mejor estrategia basada en historial.

    Patrón:
    1. Calibración: ejecuta cada estrategia en un caso separado
    2. Evaluación: elige la estrategia con menor pérdida media histórica
    3. Actualización: registra el resultado para futuras decisiones

    La selección NUNCA usa información del óptimo de la instancia actual.
    """

    def __init__(self, strategy_names: List[str],
                 quality_weight: float = 0.7,
                 cost_weight: float = 0.3):
        self.stats: Dict[str, StrategyStats] = {
            name: StrategyStats(name) for name in strategy_names
        }
        self.calibrated = False
        self.calibration_order = list(strategy_names)
        self._next_cal = 0
        self.quality_weight = quality_weight
        self.cost_weight = cost_weight

    def next_strategy(self) -> str:
        """Retorna el nombre de la siguiente estrategia a usar."""
        require("ai.query", op_desc="selector.next_strategy()")

        if not self.calibrated:
            name = self.calibration_order[self._next_cal]
            self._next_cal += 1
            if self._next_cal >= len(self.calibration_order):
                self.calibrated = True
            return name

        # Elegir la de menor pérdida media; desempate por nombre
        return min(self.stats.values(), key=lambda s: (s.mean_loss, s.name)).name

    def update(self, name: str, loss: float, quality: float, cost: float) -> None:
        """Registra el resultado de ejecutar la estrategia 'name'."""
        if name not in self.stats:
            raise ValueError(f"estrategia desconocida: {name}")
        self.stats[name].update(loss, quality, cost)

    def compute_loss(self, quality: float, quality_ref: float,
                     cost: float, cost_ref: float) -> float:
        """Calcula la pérdida ponderada: L = w_q * (1 - Q/Q_ref) + w_c * min(C/C_ref, 1)."""
        qloss = max(0.0, 1.0 - quality / max(quality_ref, 1e-12))
        closs = min(cost / max(cost_ref, 1.0), 1.0)
        return self.quality_weight * qloss + self.cost_weight * closs

    def summary(self) -> Dict[str, Any]:
        """Retorna un resumen de todas las estrategias."""
        return {name: s.to_dict() for name, s in self.stats.items()}

    def best_strategy(self) -> str:
        """Retorna el nombre de la estrategia con menor pérdida media."""
        return min(self.stats.values(), key=lambda s: s.mean_loss).name


def bootstrap_paired(adaptive_gaps: List[float], fixed_gaps: List[float],
                     n_bootstrap: int = 5000, seed: int = 909090) -> Dict[str, Any]:
    """Bootstrap pareado para comparar adaptativo vs fijo.

    Args:
        adaptive_gaps: lista de gaps del método adaptativo
        fixed_gaps: lista de gaps del método fijo (misma longitud)
        n_bootstrap: número de muestras bootstrap
        seed: semilla para reproducibilidad

    Returns:
        Dict con diferencia media, intervalo de confianza 95%, interpretación
    """
    require("ai.query", op_desc="selector.bootstrap_paired()")

    import random
    rng = random.Random(seed)
    n = len(adaptive_gaps)
    diffs = [a - f for a, f in zip(adaptive_gaps, fixed_gaps)]
    mean_diff = sum(diffs) / n if n > 0 else 0.0

    boot_means = []
    for _ in range(n_bootstrap):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()

    lo = boot_means[int(0.025 * len(boot_means))]
    hi = boot_means[min(int(0.975 * len(boot_means)), len(boot_means) - 1)]

    return {
        "mean_difference": round(mean_diff, 6),
        "ci_95": [round(lo, 6), round(hi, 6)],
        "n_bootstrap": n_bootstrap,
        "interpretation": "Valores negativos favorecen adaptativo; positivos favorecen fijo." if mean_diff < 0 else "Valores positivos favorecen fijo; negativos favorecen adaptativo.",
        "significant": (hi < 0 or lo > 0),
    }


_exports = {
    "StrategyStats": StrategyStats,
    "AdaptiveSelector": AdaptiveSelector,
    "bootstrap_paired": bootstrap_paired,
}
