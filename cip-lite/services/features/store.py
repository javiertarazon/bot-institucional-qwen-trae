"""
Feature Store - Redis + DuckDB
Almacenamiento dual para features en tiempo real e históricas.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict
import json
import structlog
import redis
import duckdb

logger = structlog.get_logger()


class FeatureStore:
    """Feature store dual: Redis (online) + DuckDB (offline)."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379",
                 duckdb_path: str = "./data/features.duckdb"):
        self.duckdb_path = duckdb_path
        self.redis_available = False
        self.redis = None
        
        # Intentar conectar a Redis
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            self.redis.ping()
            self.redis_available = True
            logger.info("redis_connected")
        except Exception as e:
            logger.warning("redis_not_available", error=str(e))
            self.redis_available = False
        
        self._init_duckdb()
        logger.info("feature_store_initialized", redis_available=self.redis_available)
    
    def _init_duckdb(self):
        """Inicializa tabla histórica en DuckDB."""
        try:
            con = duckdb.connect(self.duckdb_path)
            con.execute("""
                CREATE TABLE IF NOT EXISTS features_history (
                    signal_id VARCHAR,
                    asset VARCHAR,
                    feature_name VARCHAR,
                    feature_value DOUBLE,
                    timestamp TIMESTAMP,
                    PRIMARY KEY (signal_id, feature_name, timestamp)
                )
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_asset
                ON features_history(asset)
            """)
            con.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_ts
                ON features_history(timestamp)
            """)
            con.close()
            logger.debug("duckdb_initialized", path=self.duckdb_path)
        except Exception as e:
            logger.warning("duckdb_init_failed", error=str(e))
    
    # ═══════════ Online Serving (Redis) ═══════════
    
    def put_online(self, signal_id: str, asset: str,
                   features: Dict[str, float], ttl_seconds: int = 3600):
        """Guarda features en Redis para serving rápido."""
        if not self.redis_available:
            logger.warning("redis_not_available_skipping_put_online", signal_id=signal_id)
            return
        
        key = f"features:{signal_id}"
        data = {
            "asset": asset,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **{k: str(v) for k, v in features.items()},
        }
        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=data)
        pipe.expire(key, ttl_seconds)
        pipe.execute()
        logger.debug("feature_put_online", signal_id=signal_id, asset=asset)
    
    def get_online(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene features desde Redis (latencia < 1ms)."""
        if not self.redis_available:
            logger.warning("redis_not_available_skipping_get_online", signal_id=signal_id)
            return None
        
        key = f"features:{signal_id}"
        data = self.redis.hgetall(key)
        if not data:
            return None
        
        result = {}
        for k, v in data.items():
            if k in ("asset", "timestamp"):
                result[k] = v
            else:
                try:
                    result[k] = float(v)
                except (ValueError, TypeError):
                    result[k] = v
        return result
    
    # ═══════════ Historical Storage (DuckDB) ═══════════
    
    def put_historical(self, signal_id: str, asset: str,
                      features: Dict[str, float], timestamp: Optional[datetime] = None):
        """Guarda features históricos en DuckDB."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).replace(tzinfo=None)
        # Si es timezone-aware, convertir a naive UTC
        elif timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        
        try:
            con = duckdb.connect(self.duckdb_path)
            for feature_name, feature_value in features.items():
                con.execute("""
                    INSERT OR REPLACE INTO features_history
                    (signal_id, asset, feature_name, feature_value, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, [signal_id, asset, feature_name, feature_value, timestamp])
            con.close()
            logger.debug("feature_put_historical", signal_id=signal_id)
        except Exception as e:
            logger.error("historical_put_failed", error=str(e))
    
    def get_historical(self, asset: str, start_time: datetime,
                      end_time: Optional[datetime] = None) -> Optional[list]:
        """Obtiene features históricos para un activo."""
        if end_time is None:
            end_time = datetime.now(timezone.utc).replace(tzinfo=None)
        # Si es timezone-aware, convertir a naive UTC
        elif end_time.tzinfo is not None:
            end_time = end_time.astimezone(timezone.utc).replace(tzinfo=None)
        # Convertir start_time también si es timezone-aware
        if start_time.tzinfo is not None:
            start_time = start_time.astimezone(timezone.utc).replace(tzinfo=None)
        
        try:
            con = duckdb.connect(self.duckdb_path)
            df = con.execute("""
                SELECT * FROM features_history
                WHERE asset = ? AND timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, [asset, start_time, end_time]).fetchdf()
            con.close()
            return df
        except Exception as e:
            logger.error("historical_get_failed", error=str(e))
            return None
