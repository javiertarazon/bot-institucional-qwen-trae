"""
Tests extendidos para Feature Store
"""
import pytest
import tempfile
import os
import time
from datetime import datetime, timedelta, timezone
from services.features.store import FeatureStore


class MockRedis:
    """Mock Redis client"""
    def __init__(self):
        self.data = {}
        self.ping_called = False

    def ping(self):
        self.ping_called = True

    def pipeline(self):
        return MockPipeline(self)

    def hgetall(self, key):
        return self.data.get(key, {})


class MockPipeline:
    """Mock Redis pipeline"""
    def __init__(self, redis):
        self.redis = redis
        self.commands = []
        self.key = None
        self.data = None
        self.ttl = None

    def hset(self, key, mapping):
        self.key = key
        self.data = mapping
        return self

    def expire(self, key, ttl):
        self.ttl = ttl
        return self

    def execute(self):
        if self.key and self.data:
            self.redis.data[self.key] = self.data


class TestFeatureStoreExtended:
    """Tests extendidos para Feature Store"""
    
    def test_init_duckdb_failed(self, monkeypatch):
        """Verifica el manejo de fallos al inicializar DuckDB"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Monkeypatch duckdb.connect para lanzar una excepción
            def mock_connect(*args, **kwargs):
                raise Exception("Error de prueba")
            
            monkeypatch.setattr("services.features.store.duckdb.connect", mock_connect)
            
            store = FeatureStore(
                redis_url="redis://invalid:6379",
                duckdb_path=os.path.join(temp_dir, "test.duckdb")
            )
            
            # Debería marcar redis como no disponible y no fallar
            assert store.redis_available is False
    
    def test_put_historical_with_timezone(self):
        """Verifica el guardado de features con timestamp timezone-aware"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)
            
            # Crear timestamp con timezone
            ts = datetime.now(timezone.utc).replace(tzinfo=None)
            store.put_historical(
                signal_id="test_timezone",
                asset="BTC",
                features={"volatility": 0.2, "rsi": 50.0},
                timestamp=ts
            )
            
            # Verificar que se guardó correctamente
            start_time = ts - timedelta(hours=1)
            end_time = ts + timedelta(hours=1)
            df = store.get_historical("BTC", start_time, end_time)
            assert df is not None
            assert len(df) == 2
    
    def test_get_historical_with_timezone(self):
        """Verifica la consulta con timestamps timezone-aware"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)
            
            ts = datetime.now(timezone.utc).replace(tzinfo=None)
            store.put_historical("test_tz", "ETH", {"price": 3000.0}, timestamp=ts)
            
            start_time = ts - timedelta(hours=1)
            end_time = ts + timedelta(hours=1)
            # Convertir a timezone-aware
            start_tz = start_time.replace(tzinfo=timezone.utc)
            end_tz = end_time.replace(tzinfo=timezone.utc)
            
            df = store.get_historical("ETH", start_tz, end_tz)
            assert df is not None
            assert len(df) == 1
    
    def test_put_online_redis_not_available(self):
        """Verifica put_online cuando Redis no está disponible"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)
            
            # No debería lanzar excepción
            store.put_online(
                signal_id="test_redis_offline",
                asset="BTC",
                features={"sentiment": 0.5}
            )
    
    def test_get_online_redis_not_available(self):
        """Verifica get_online cuando Redis no está disponible"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)
            
            result = store.get_online("test_redis_offline")
            assert result is None

    def test_put_and_get_online_redis_available(self, monkeypatch):
        """Verifica put_online y get_online con Redis disponible"""
        mock_redis = MockRedis()

        def mock_from_url(*args, **kwargs):
            return mock_redis

        monkeypatch.setattr("services.features.store.redis.from_url", mock_from_url)

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://localhost:6379", duckdb_path=db_path)

            # Put online
            store.put_online(
                signal_id="test_online",
                asset="BTC",
                features={"sentiment": 0.5, "price": 50000.0}
            )

            # Get online
            result = store.get_online("test_online")
            assert result is not None
            assert result["asset"] == "BTC"
            assert result["sentiment"] == 0.5
            assert result["price"] == 50000.0

            # Get non-existent key
            result_none = store.get_online("non_existent")
            assert result_none is None

    def test_put_historical_failed(self, monkeypatch):
        """Verifica manejo de errores en put_historical"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)

            def mock_connect(*args, **kwargs):
                raise Exception("Error de prueba")

            monkeypatch.setattr("services.features.store.duckdb.connect", mock_connect)

            # No debería lanzar excepción
            store.put_historical(
                signal_id="test_error",
                asset="BTC",
                features={"price": 50000.0}
            )

    def test_get_historical_failed(self, monkeypatch):
        """Verifica manejo de errores en get_historical"""
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.duckdb")
            store = FeatureStore(redis_url="redis://invalid:6379", duckdb_path=db_path)

            def mock_connect(*args, **kwargs):
                raise Exception("Error de prueba")

            monkeypatch.setattr("services.features.store.duckdb.connect", mock_connect)

            result = store.get_historical("BTC", datetime.now(timezone.utc).replace(tzinfo=None))
            assert result is None
