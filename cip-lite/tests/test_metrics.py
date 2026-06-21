"""
Tests para el módulo de métricas
"""
import pytest
import time
from services.metrics import LRUCache, MetricsCollector, OptimizedFeatureStore


def test_lru_cache_ttl():
    """Test that TTL works correctly in LRUCache"""
    cache = LRUCache(max_size=10, ttl_seconds=1)
    cache.set("test_key", "test_value")
    assert cache.get("test_key") == "test_value"
    time.sleep(1.1)  # Wait for TTL to expire
    assert cache.get("test_key") is None


def test_lru_cache_eviction():
    """Test that LRUCache evicts least recently used items"""
    cache = LRUCache(max_size=3)
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.set("key3", "value3")
    # Access key1 to make it recently used
    assert cache.get("key1") == "value1"
    cache.set("key4", "value4")
    # Key2 should be evicted
    assert cache.get("key2") is None
    assert cache.get("key1") == "value1"


def test_metrics_collector_prometheus_disabled(monkeypatch):
    """Test MetricsCollector when Prometheus is not available"""
    monkeypatch.setattr("services.metrics.HAS_PROMETHEUS", False)
    metrics = MetricsCollector()
    assert metrics.latency_histogram is None
    assert metrics.request_counter is None
    assert metrics.cache_hits_gauge is None
    assert metrics.cache_misses_gauge is None
    assert metrics.cpu_gauge is None
    assert metrics.memory_gauge is None


def test_track_latency_decorator():
    """Test that the track_latency decorator works correctly"""
    metrics = MetricsCollector()
    
    @metrics.track_latency("test_endpoint")
    def test_func(x: int):
        return x * 2
    
    result = test_func(5)
    assert result == 10


def test_track_latency_decorator_exception():
    """Test that the track_latency decorator handles exceptions"""
    metrics = MetricsCollector()
    
    @metrics.track_latency("test_endpoint_error")
    def test_func_error():
        raise ValueError("Test error")
    
    with pytest.raises(ValueError):
        test_func_error()


def test_optimized_feature_store():
    """Test OptimizedFeatureStore"""
    fetch_calls = []
    
    def mock_fetch() -> str:
        fetch_calls.append("called")
        return "fetched_data"
    
    store = OptimizedFeatureStore()
    # First call should trigger fetch
    assert store.get_cached_data("key", mock_fetch) == "fetched_data"
    assert len(fetch_calls) == 1
    # Second call should use cache
    assert store.get_cached_data("key", mock_fetch) == "fetched_data"
    assert len(fetch_calls) == 1
