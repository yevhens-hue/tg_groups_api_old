# metrics.py
import time
from collections import defaultdict
from typing import Dict, Any
from datetime import datetime

import structlog

logger = structlog.get_logger()


class MetricsCollector:
    """
    Простой in-memory коллектор метрик.
    Для продакшена лучше использовать Prometheus или StatsD.
    """

    def __init__(self):
        self._request_counts: Dict[str, int] = defaultdict(int)
        self._request_times: Dict[str, list] = defaultdict(list)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_request(self, endpoint: str, status_code: int, duration: float):
        """Записать метрику запроса."""
        self._request_counts[endpoint] += 1
        
        if status_code >= 400:
            self._error_counts[endpoint] += 1
        
        # Храним только последние 1000 значений для каждого эндпоинта
        if len(self._request_times[endpoint]) >= 1000:
            self._request_times[endpoint].pop(0)
        self._request_times[endpoint].append(duration)

    def get_latency_percentiles(self, endpoint: str) -> Dict[str, float]:
        """Получить перцентили латентности для эндпоинта."""
        times = self._request_times[endpoint]
        if not times:
            return {}

        sorted_times = sorted(times)
        length = len(sorted_times)

        return {
            "p50": sorted_times[int(length * 0.50)] if length > 0 else 0,
            "p75": sorted_times[int(length * 0.75)] if length > 0 else 0,
            "p90": sorted_times[int(length * 0.90)] if length > 0 else 0,
            "p95": sorted_times[int(length * 0.95)] if length > 0 else 0,
            "p99": sorted_times[int(length * 0.99)] if length > 0 else 0,
        }

    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику."""
        uptime = time.time() - self._start_time
        
        stats = {
            "uptime_seconds": round(uptime, 2),
            "endpoints": {},
        }

        for endpoint in self._request_counts:
            request_count = self._request_counts[endpoint]
            error_count = self._error_counts[endpoint]
            times = self._request_times[endpoint]
            
            avg_time = sum(times) / len(times) if times else 0
            percentiles = self.get_latency_percentiles(endpoint)
            
            stats["endpoints"][endpoint] = {
                "total_requests": request_count,
                "errors": error_count,
                "success_rate": round((request_count - error_count) / request_count * 100, 2) if request_count > 0 else 0,
                "avg_response_time_ms": round(avg_time * 1000, 2),
                "latency_percentiles_ms": {
                    k: round(v * 1000, 2) for k, v in percentiles.items()
                },
                "requests_per_second": round(request_count / uptime, 2) if uptime > 0 else 0,
            }

        return stats

    def reset(self):
        """Сбросить метрики."""
        self._request_counts.clear()
        self._request_times.clear()
        self._error_counts.clear()
        self._start_time = time.time()


# Глобальный коллектор метрик
_metrics_collector: MetricsCollector = None


def get_metrics_collector() -> MetricsCollector:
    """Получить глобальный коллектор метрик."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector

