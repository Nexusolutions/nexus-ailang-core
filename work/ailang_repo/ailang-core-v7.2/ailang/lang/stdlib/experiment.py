"""Stdlib `experiment` — Framework de benchmark científico (Q4).

Proporciona primitivas para experimentos reproducibles:
- Hipótesis predefinida
- Semillas fijas
- Calibración separada
- Bootstrap pareado
- Reporte JSON reproducible
"""
from __future__ import annotations

import json
import platform
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ailang.runtime.capabilities import require
from ailang.lang.stdlib.selector import AdaptiveSelector, bootstrap_paired


@dataclass
class Experiment:
    """Experimento científico reproducible."""
    name: str
    hypothesis: str = ""
    seeds: List[int] = field(default_factory=list)
    baselines: List[str] = field(default_factory=list)
    methods: List[str] = field(default_factory=list)
    calibration_seed: int = 424242
    results: Dict[str, List[Dict]] = field(default_factory=dict)
    per_instance: List[Dict] = field(default_factory=list)

    def set_hypothesis(self, h: str) -> "Experiment":
        self.hypothesis = h
        return self

    def set_seeds(self, seeds: List[int]) -> "Experiment":
        self.seeds = list(seeds)
        return self

    def set_baselines(self, names: List[str]) -> "Experiment":
        self.baselines = list(names)
        for name in names:
            self.results[name] = []
        return self

    def set_methods(self, names: List[str]) -> "Experiment":
        self.methods = list(names)
        for name in names:
            if name not in self.results:
                self.results[name] = []
        return self

    def record(self, method: str, seed: int, result: Dict[str, Any]) -> None:
        """Registra el resultado de un método en una semilla."""
        entry = {"seed": seed, **result}
        if method not in self.results:
            self.results[method] = []
        self.results[method].append(entry)

    def compute_gap(self, value: float, optimal: float) -> float:
        """Gap relativo al óptimo."""
        return (optimal - value) / max(optimal, 1e-12)

    def summary(self) -> Dict[str, Any]:
        """Genera resumen estadístico de todos los métodos."""
        from ailang.lang.stdlib.graph import maxcut_gap  # avoid circular import
        summary = {}
        for method, records in self.results.items():
            if not records:
                continue
            gaps = [r.get("gap", 0) for r in records]
            evals = [r.get("evaluations", 0) for r in records]
            optimal_rate = sum(1 for g in gaps if g <= 1e-12) / len(gaps)
            summary[method] = {
                "mean_gap": sum(gaps) / len(gaps),
                "median_gap": sorted(gaps)[len(gaps) // 2],
                "min_gap": min(gaps),
                "max_gap": max(gaps),
                "optimal_rate": optimal_rate,
                "mean_evaluations": sum(evals) / len(evals),
            }
        return summary

    def bootstrap_comparison(self, method_a: str, method_b: str,
                             n_bootstrap: int = 5000, seed: int = 909090) -> Dict:
        """Compara dos métodos con bootstrap pareado."""
        gaps_a = [r.get("gap", 0) for r in self.results.get(method_a, [])]
        gaps_b = [r.get("gap", 0) for r in self.results.get(method_b, [])]
        if len(gaps_a) != len(gaps_b) or not gaps_a:
            return {"error": "métodos deben tener el mismo número de resultados"}
        return bootstrap_paired(gaps_a, gaps_b, n_bootstrap, seed)

    def report(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Genera reporte JSON reproducible."""
        require("ai.query", op_desc="experiment.report()")

        result = {
            "experiment": self.name,
            "hypothesis": self.hypothesis,
            "seeds": self.seeds,
            "calibration_seed": self.calibration_seed,
            "summary": self.summary(),
            "environment": {
                "python": sys.version,
                "platform": platform.platform(),
            },
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Reporte guardado en: {path}")

        return result


def create(name: str) -> Experiment:
    """Crea un nuevo experimento."""
    require("ai.query", op_desc="experiment.create()")
    return Experiment(name=name)


_exports = {
    "Experiment": Experiment,
    "create": create,
}
