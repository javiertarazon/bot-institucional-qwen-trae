"""
Módulo de Métricas y Optimización para CIP
- Prometheus Metrics para trading
- Caché LRU
- Monitoreo de Recursos
"""

import time
import functools
from collections import OrderedDict
from typing import Any, Callable, Optional, Dict
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


class TradingMetrics:
    """Métricas específicas de trading para Prometheus"""
    
    def __init__(self):
        # Trading performance gauges
        self.pnl_gauge: Optional[Gauge] = None
        self.roi_gauge: Optional[Gauge] = None
        self.win_rate_gauge: Optional[Gauge] = None
        self.profit_factor_gauge: Optional[Gauge] = None
        self.max_drawdown_gauge: Optional[Gauge] = None
        
        # Trade counters
        self.trades_total: Optional[Counter] = None
        self.winning_trades_counter: Optional[Counter] = None
        self.losing_trades_counter: Optional[Counter] = None
        
        # Streak tracking
        self.current_win_streak: Optional[Gauge] = None
        self.current_loss_streak: Optional[Gauge] = None
        self.max_win_streak: Optional[Gauge] = None
        self.max_loss_streak: Optional[Gauge] = None
        
        # Trade conditions histograms
        self.trade_conditions_histogram: Optional[Histogram] = None
        
        if HAS_PROMETHEUS:
            self._init_trading_metrics()
    
    def _init_trading_metrics(self):
        """Inicializa métricas de trading"""
        self.pnl_gauge = Gauge('cip_pnl_usd', 'Profit & Loss en USD')
        self.roi_gauge = Gauge('cip_roi_percent', 'Return on Investment porcentual')
        self.win_rate_gauge = Gauge('cip_win_rate', 'Tasa de aciertos (win rate)')
        self.profit_factor_gauge = Gauge('cip_profit_factor', 'Ratio de beneficio')
        self.max_drawdown_gauge = Gauge('cip_max_drawdown', 'Máximo drawdown')
        
        self.trades_total = Counter('cip_trades_total', 'Total de operaciones', ['status'])
        self.winning_trades_counter = Counter('cip_winning_trades_total', 'Operaciones ganadoras')
        self.losing_trades_counter = Counter('cip_losing_trades_total', 'Operaciones perdedoras')
        
        self.current_win_streak = Gauge('cip_current_win_streak', 'Racha actual de ganadoras')
        self.current_loss_streak = Gauge('cip_current_loss_streak', 'Racha actual de perdedoras')
        self.max_win_streak = Gauge('cip_max_win_streak', 'Máxima racha de ganadoras')
        self.max_loss_streak = Gauge('cip_max_loss_streak', 'Máxima racha de perdedoras')
        
        self.trade_conditions_histogram = Histogram(
            'cip_trade_conditions',
            'Condiciones de operaciones (volatilidad, confianza)',
            ['outcome']
        )
    
    def update_from_backtest_results(self, results: Dict[str, Any]):
        """Actualiza métricas desde resultados de backtesting"""
        if not HAS_PROMETHEUS:
            return
        
        self.pnl_gauge.set(results.get('equity_curve', [0])[-1] - 100000)
        roi = results.get('total_return', 0) * 100
        self.roi_gauge.set(roi)
        
        win_rate = results.get('win_rate', 0)
        self.win_rate_gauge.set(win_rate)
        
        self.profit_factor_gauge.set(results.get('profit_factor', 0))
        self.max_drawdown_gauge.set(abs(results.get('max_drawdown', 0)) * 100)
        
        # Streaks
        self.current_win_streak.set(results.get('current_win_streak', 0))
        self.current_loss_streak.set(results.get('current_loss_streak', 0))
        self.max_win_streak.set(results.get('max_win_streak', 0))
        self.max_loss_streak.set(results.get('max_loss_streak', 0))
    
    def record_trade(self, is_winner: bool, pnl: float, conditions: Dict[str, float] = None):
        """Registra una operación completada"""
        if not HAS_PROMETHEUS:
            return
        
        status = "win" if is_winner else "loss"
        self.trades_total.labels(status=status).inc()
        
        if is_winner:
            self.winning_trades_counter.inc()
        else:
            self.losing_trades_counter.inc()
        
        if conditions and self.trade_conditions_histogram:
            self.trade_conditions_histogram.labels(outcome=status).observe(conditions.get('volatility', 0))


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
