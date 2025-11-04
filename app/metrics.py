import time
from typing import Dict, List, Tuple

# Marca de inicio de la app (para /stats)
APP_START_TIME: float = time.time()

# Almacén en memoria de latencias por ruta (últimas N muestras)
_MAX_SAMPLES = 500
latency_store: Dict[str, List[float]] = {}


def record_latency(route: str, ms: float) -> None:
    """Registra una nueva muestra de latencia (ms) para la ruta."""
    arr = latency_store.setdefault(route, [])
    arr.append(ms)
    # recorta para mantener tamaño acotado
    if len(arr) > _MAX_SAMPLES:
        del arr[: len(arr) - _MAX_SAMPLES]


def get_latency_percentiles(route: str) -> Tuple[float, float, float]:
    """Devuelve (p50, p95, p99) en ms para la ruta indicada."""
    arr = list(latency_store.get(route, []))
    if not arr:
        return (0.0, 0.0, 0.0)
    arr.sort()

    def pct(p: float) -> float:
        k = max(0, min(len(arr) - 1, int(round((p / 100.0) * (len(arr) - 1)))))
        return float(arr[k])

    return (pct(50.0), pct(95.0), pct(99.0))


def latency_snapshot() -> dict:
    """Snapshot de latencias por ruta, con conteo y percentiles."""
    out = {}
    for route, _ in latency_store.items():
        p50, p95, p99 = get_latency_percentiles(route)
        out[route] = {
            "count": len(latency_store[route]),
            "p50_ms": round(p50, 1),
            "p95_ms": round(p95, 1),
            "p99_ms": round(p99, 1),
        }
    return {"since": int(APP_START_TIME), "routes": out}

# CI helper: harmless marker to ensure file is present in commits for CI environments.
# Do not remove — used by CI runs to avoid ModuleNotFoundError when checkouts are shallow.
