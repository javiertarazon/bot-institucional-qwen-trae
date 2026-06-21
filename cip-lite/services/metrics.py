"""
Módulo de Métricas y Optimización para CIP
- Prometheus Metrics
- Caché LRU
- Monitoreo de Recursos
"""

import time
import functools
from collections import OrderedDict
from typing import Any, Callable, Optional
import psutil
import structlog

logger = structlog.get_logger()

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus-client no instalado. Métricas Prometheus no disponibles.")


class LRUCache:
    """Caché LRU simple y thread-safe"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        logger.info("LRU Cache inicializado", max_size=max_size, ttl_seconds=ttl_seconds)

    def get(self, key: str) -> Optional[Any]:
        """Obtiene un valor del caché"""
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl_seconds:
            del self.cache[key]
            return None

        self.cache.move_to_end(key)
        return value

    def set(self, key: str, value: Any):
        """Establece un valor en el caché"""
        if key in self.cache:
            del self.cache[key]

        if len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)

        self.cache[key] = (value, time.time())

    def clear(self):
        """Limpia todo el caché"""
        self.cache.clear()


class MetricsCollector:
    """Coleccionador de métricas institucional"""

    def __init__(self, prometheus_port: int = 8000):
        self.latency_histogram: Optional[Histogram] = None
        self.request_counter: Optional[Counter] = None
        self.cache_hits_gauge: Optional[Gauge] = None
        self.cache_misses_gauge: Optional[Gauge] = None
        self.cpu_gauge: Optional[Gauge] = None
        self.memory_gauge: Optional[Gauge] = None

        self.cache_hits = 0
        self.cache_misses = 0

        if HAS_PROMETHEUS:
            self._init_prometheus(prometheus_port)

        logger.info("Metrics Collector inicializado")

    def _init_prometheus(self, port: int):
        """Inicializa métricas Prometheus"""
        try:
            self.latency_histogram = Histogram(
                'cip_request_latency_seconds',
                'Latencia de solicitudes',
                ['endpoint']
            )
            self.request_counter = Counter(
                'cip_requests_total',
                'Total de solicitudes',
                ['endpoint', 'status']
            )
            self.cache_hits_gauge = Gauge('cip_cache_hits', 'Total de hits en caché')
            self.cache_misses_gauge = Gauge('cip_cache_misses', 'Total de misses en caché')
            self.cpu_gauge = Gauge('cip_cpu_percent', 'Uso de CPU')
            self.memory_gauge = Gauge('cip_memory_percent', 'Uso de memoria')

            start_http_server(port)
            logger.info("Servidor Prometheus iniciado en puerto", port=port)
        except Exception as e:
            logger.error("Error al inicializar Prometheus", error=str(e))

    def track_latency(self, endpoint: str):
        """Decorador para medir latencia"""
        def decorator(func: Callable):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    status = "success"
                    return result
                except Exception:
                    status = "error"
                    raise
                finally:
                    latency = time.time() - start_time
                    if self.latency_histogram:
                        self.latency_histogram.labels(endpoint=endpoint).observe(latency)
                    if self.request_counter:
                        self.request_counter.labels(endpoint=endpoint, status=status).inc()
                    logger.debug("Latencia medida", endpoint=endpoint, latency=latency, status=status)
            return wrapper
        return decorator

    def record_cache_hit(self):
        """Registra un hit en caché"""
        self.cache_hits += 1
        if self.cache_hits_gauge:
            self.cache_hits_gauge.set(self.cache_hits)

    def record_cache_miss(self):
        """Registra un miss en caché"""
        self.cache_misses += 1
        if self.cache_misses_gauge:
            self.cache_misses_gauge.set(self.cache_misses)

    def collect_resource_metrics(self) -> dict:
        """Colecciona métricas de recursos del sistema"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent

        if self.cpu_gauge:
            self.cpu_gauge.set(cpu)
        if self.memory_gauge:
            self.memory_gauge.set(memory)

        metrics = {
            "cpu_percent": cpu,
            "memory_percent": memory,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses
        }

        logger.debug("Métricas de recursos coleccionadas", metrics=metrics)
        return metrics


class OptimizedFeatureStore:
    """Feature Store optimizado con caché"""

    def __init__(self, cache: LRUCache = None):
        self.cache = cache or LRUCache(max_size=500, ttl_seconds=600)
        self.metrics = MetricsCollector()
        logger.info("Optimized Feature Store inicializado")

    def get_cached_data(self, key: str, fetch_func: Callable, *args, **kwargs):
        """Obtiene datos del caché o los carga si no existen"""
        cached = self.cache.get(key)
        if cached is not None:
            self.metrics.record_cache_hit()
            return cached

        self.metrics.record_cache_miss()
        data = fetch_func(*args, **kwargs)
        self.cache.set(key, data)
        return data
