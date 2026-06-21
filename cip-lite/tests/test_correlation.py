"""
Tests para módulo de correlación de activos
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from services.correlation.engine import (
    AssetClass, AssetData, CorrelationResult, CorrelationEngine
)


class TestAssetData:
    """Tests para la clase AssetData"""

    def test_initialization(self):
        """Verifica la inicialización"""
        dates = pd.date_range(start='2024-01-01', periods=30)
        prices = pd.Series(np.random.randn(30).cumsum() + 50000, index=dates)
        asset_data = AssetData(
            symbol="BTC",
            asset_class=AssetClass.CRYPTO,
            prices=prices
        )
        
        assert asset_data.symbol == "BTC"
        assert asset_data.asset_class == AssetClass.CRYPTO
        assert len(asset_data.prices) == 30


class TestCorrelationEngine:
    """Tests para CorrelationEngine"""

    def test_initialization(self):
        """Verifica la inicialización del motor de correlación"""
        engine = CorrelationEngine()
        assert engine is not None
        assert hasattr(engine, 'exchange')

    def test_calculate_correlation_matrix(self):
        """Verifica el cálculo de la matriz de correlación"""
        engine = CorrelationEngine()
        
        # Crear datos de prueba
        dates = pd.date_range(start='2024-01-01', periods=100)
        assets = []
        for i, symbol in enumerate(['BTC', 'ETH', 'SOL']):
            # Precios con distintas correlaciones
            base = np.random.randn(100).cumsum() + 50000
            if i == 0:
                prices = pd.Series(base, index=dates)
            else:
                # Correlacionar con el primer activo
                prices = pd.Series(base * (1 + 0.5 * np.random.randn(100)), index=dates)
            assets.append(AssetData(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO,
                prices=prices
            ))
        
        matrix = engine.calculate_correlation_matrix(assets)
        
        assert isinstance(matrix, pd.DataFrame)
        assert len(matrix.columns) == 3
        assert len(matrix.index) == 3
        # La diagonal debe ser 1 (correlación consigo mismo)
        assert all(np.isclose(matrix.iloc[i, i], 1.0) for i in range(3))

    def test_get_correlation_pair(self):
        """Verifica el cálculo de correlación entre dos activos"""
        engine = CorrelationEngine()
        
        dates = pd.date_range(start='2024-01-01', periods=100)
        prices1 = pd.Series(np.random.randn(100).cumsum() + 50000, index=dates)
        prices2 = pd.Series(prices1 * (1 + 0.3 * np.random.randn(100)), index=dates)
        
        asset1 = AssetData(
            symbol="BTC",
            asset_class=AssetClass.CRYPTO,
            prices=prices1
        )
        asset2 = AssetData(
            symbol="ETH",
            asset_class=AssetClass.CRYPTO,
            prices=prices2
        )
        
        result = engine.get_correlation_pair(asset1, asset2)
        
        assert isinstance(result, CorrelationResult)
        assert result.asset_1 == "BTC"
        assert result.asset_2 == "ETH"
        assert -1.0 <= result.correlation <= 1.0

    def test_find_uncorrelated_assets(self):
        """Verifica la búsqueda de activos no correlacionados"""
        engine = CorrelationEngine()
        
        dates = pd.date_range(start='2024-01-01', periods=100)
        assets = []
        for symbol in ['BTC', 'ETH', 'SOL', 'ADA']:
            prices = pd.Series(np.random.randn(100).cumsum() + 50000, index=dates)
            assets.append(AssetData(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO,
                prices=prices
            ))
        
        uncorrelated = engine.find_uncorrelated_assets(
            assets,
            target_asset='BTC',
            max_correlation=0.8
        )
        
        assert isinstance(uncorrelated, list)

    def test_get_diversification_recommendations(self):
        """Verifica la obtención de recomendaciones de diversificación"""
        engine = CorrelationEngine()
        
        dates = pd.date_range(start='2024-01-01', periods=100)
        assets = []
        for symbol in ['BTC', 'ETH', 'SOL']:
            prices = pd.Series(np.random.randn(100).cumsum() + 50000, index=dates)
            assets.append(AssetData(
                symbol=symbol,
                asset_class=AssetClass.CRYPTO,
                prices=prices
            ))
        
        recommendations = engine.get_diversification_recommendations(
            assets,
            max_correlation=0.7
        )
        
        assert isinstance(recommendations, dict)
        assert "high_correlation_pairs" in recommendations
        assert "low_correlation_pairs" in recommendations
        assert "suggestions" in recommendations
    
    def test_get_diversification_recommendations_high_corr(self):
        """Verifica la obtención de recomendaciones de diversificación con pares altamente correlacionados"""
        engine = CorrelationEngine()
        
        dates = pd.date_range(start='2024-01-01', periods=100)
        # Crear dos activos altamente correlacionados
        base = np.random.randn(100).cumsum()
        prices1 = pd.Series(base + 50000, index=dates)
        prices2 = pd.Series(base + 0.01 * np.random.randn(100) + 50000, index=dates)
        
        assets = [
            AssetData(symbol="BTC", asset_class=AssetClass.CRYPTO, prices=prices1),
            AssetData(symbol="ETH", asset_class=AssetClass.CRYPTO, prices=prices2),
        ]
        
        recommendations = engine.get_diversification_recommendations(
            assets,
            max_correlation=0.4
        )
        
        # Debería haber un par de alta correlación y una sugerencia
        assert len(recommendations["high_correlation_pairs"]) == 1
        assert len(recommendations["suggestions"]) == 1
    
    @pytest.mark.asyncio
    async def test_fetch_historical_data(self):
        """Verifica la obtención de datos históricos"""
        engine = CorrelationEngine()
        asset_data = await engine.fetch_historical_data("BTC", AssetClass.CRYPTO, days=30)
        assert asset_data.symbol == "BTC"
        assert asset_data.asset_class == AssetClass.CRYPTO
        assert len(asset_data.prices) == 30

    @pytest.mark.asyncio
    async def test_fetch_historical_data_error(self, monkeypatch):
        """Verifica el manejo de errores en la obtención de datos históricos"""
        def mock_now():
            raise Exception("Simulated error")
        
        monkeypatch.setattr("pandas.Timestamp.now", mock_now)
        engine = CorrelationEngine()
        with pytest.raises(Exception):
            await engine.fetch_historical_data("BTC", AssetClass.CRYPTO, days=30)

    def test_find_uncorrelated_assets_invalid(self):
        """Verifica que levante un error para un activo objetivo no válido"""
        engine = CorrelationEngine()
        dates = pd.date_range(start='2024-01-01', periods=30)
        asset = AssetData(
            symbol="BTC",
            asset_class=AssetClass.CRYPTO,
            prices=pd.Series(np.random.randn(30).cumsum() + 50000, index=dates)
        )
        with pytest.raises(ValueError):
            engine.find_uncorrelated_assets([asset], target_asset="INVALID")
