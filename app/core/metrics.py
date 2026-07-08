from collections import defaultdict
from threading import Lock
from time import monotonic


class Metrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._histograms: dict[str, list[float]] = defaultdict(list)
        self._max_samples = 1000

    def incr(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self._counters[name] += amount

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            samples = self._histograms[name]
            samples.append(value)
            if len(samples) > self._max_samples:
                samples.pop(0)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            out: dict[str, object] = {}
            for name, value in self._counters.items():
                out[name] = value
            for name, samples in self._histograms.items():
                if not samples:
                    continue
                sorted_samples = sorted(samples)
                count = len(sorted_samples)
                out[f"{name}_count"] = count
                out[f"{name}_sum"] = round(sum(sorted_samples), 6)
                out[f"{name}_avg"] = round(sum(sorted_samples) / count, 6)
                out[f"{name}_p95"] = round(sorted_samples[min(count - 1, int(count * 0.95))], 6)
                out[f"{name}_max"] = round(sorted_samples[-1], 6)
            return out


metrics = Metrics()


class Timer:
    def __init__(self, metric_name: str) -> None:
        self.metric_name = metric_name
        self._start = 0.0

    def __enter__(self) -> "Timer":
        self._start = monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        duration = monotonic() - self._start
        metrics.observe(self.metric_name, duration)
        if exc_type is not None:
            metrics.incr(f"{self.metric_name}_errors")
