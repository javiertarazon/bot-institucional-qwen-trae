"""
Tests para el módulo Feature Store.
"""
import pytest
from datetime import datetime, timedelta, timezone
from services.features.store import FeatureStore


class TestFeatureStore:
    """Suite de tests para FeatureStore."""
    
    def test_initialization(self):
        """Test que verifica la inicialización correcta del FeatureStore."""
        store = FeatureStore()
        assert store is not None
        assert hasattr(store, "redis_available")
        assert hasattr(store, "duckdb_path")
    
    def test_put_historical(self, tmp_path):
        """Test que verifica el almacenamiento histórico."""
        # Usar un path temporal para DuckDB
        test_db_path = tmp_path / "test_features.duckdb"
        store = FeatureStore(duckdb_path=str(test_db_path))
        
        features = {
            "sentiment_score": 0.8,
            "volatility": 0.05
        }
        
        # No debería lanzar excepciones
        store.put_historical(
            signal_id="test_123",
            asset="BTC",
            features=features
        )
        
        # Verificar que se puede recuperar
        one_hour_ago = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        df = store.get_historical("BTC", one_hour_ago)
        assert df is not None
        assert len(df) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
