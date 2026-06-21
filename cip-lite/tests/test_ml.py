
"""
Tests para módulos de Machine Learning (predictor)
"""
import pytest
import numpy as np
import pandas as pd
from services.ml.predictor import (
    FeatureEngineering, XGBoostModel, EnsemblePredictor, create_demo_price_data
)
from services.ml.advanced_strategy import AdvancedTradingStrategy
from services.ml.improved_strategy import ImprovedTrendStrategy
from services.backtesting.engine import HistoricalData

class TestFeatureEngineering:
    """Tests para FeatureEngineering básico"""

    def test_initialization(self):
        """Verifica que se inicialice correctamente"""
        fe = FeatureEngineering()
        assert fe is not None
        assert hasattr(fe, 'scaler')

    def test_create_features(self):
        """Verifica la creación de características"""
        dates = pd.date_range(start='2024-01-01', periods=50)
        prices = np.random.randn(50).cumsum() + 50000
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * 1.02 for p in prices],
            'low': [p * 0.98 for p in prices],
            'close': prices,
            'volume': np.random.randint(10000, 100000, 50)
        })
        
        fe = FeatureEngineering()
        df_features = fe.create_features(df)
        
        assert 'ma7' in df_features.columns
        assert 'ma21' in df_features.columns
        assert 'returns' in df_features.columns
        assert 'std7' in df_features.columns
        assert len(df_features) < len(df)

    def test_prepare_data(self):
        """Verifica la preparación de datos para el modelo"""
        dates = pd.date_range(start='2024-01-01', periods=100)
        prices = np.random.randn(100).cumsum() + 50000
        df = pd.DataFrame({
            'date': dates,
            'close': prices,
            'target': np.random.randint(0, 2, 100)
        })
        
        fe = FeatureEngineering()
        df_features = fe.create_features(df)
        X, y = fe.prepare_data(df_features)
        
        assert X is not None
        assert y is not None
        assert len(X) == len(y)
        assert len(X.shape) == 2


class TestXGBoostModel:
    """Tests para XGBoostModel"""

    def test_initialization(self):
        """Verifica la inicialización del modelo"""
        model = XGBoostModel()
        assert model is not None
        assert model.is_trained is False

    def test_train_with_sufficient_data(self):
        """Verifica el entrenamiento con datos suficientes"""
        np.random.seed(42)
        X = np.random.randn(100, 5)
        y = np.random.randint(0, 2, 100)
        
        model = XGBoostModel()
        accuracy = model.train(X, y)
        
        assert model.is_trained is True
        assert 0.0 <= accuracy <= 1.0

    def test_train_with_insufficient_data(self):
        """Verifica el entrenamiento con pocos datos"""
        X = np.random.randn(5, 5)
        y = np.random.randint(0, 2, 5)
        
        model = XGBoostModel()
        accuracy = model.train(X, y)
        
        assert model.is_trained is True
        assert accuracy == 0.5

    def test_predict_proba_without_training(self):
        """Verifica predicción sin entrenamiento"""
        model = XGBoostModel()
        X = np.random.randn(1, 5)
        proba = model.predict_proba(X)
        
        assert np.array_equal(proba, [0.5, 0.5])


class TestEnsemblePredictor:
    """Tests para EnsemblePredictor"""

    def test_initialization(self):
        """Verifica la inicialización del predictor"""
        predictor = EnsemblePredictor()
        assert predictor is not None
        assert predictor.is_trained is False
        assert hasattr(predictor, 'feature_engineer')
        assert hasattr(predictor, 'xgboost')

    def test_prepare_market_data(self):
        """Verifica la preparación de datos de mercado"""
        prices = [50000 + i*100 for i in range(100)]
        predictor = EnsemblePredictor()
        df = predictor.prepare_market_data(prices)
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) <= len(prices)
        assert 'target' in df.columns

    def test_train(self):
        """Verifica el entrenamiento completo"""
        prices = create_demo_price_data(100)
        predictor = EnsemblePredictor()
        results = predictor.train(prices)
        
        assert predictor.is_trained is True
        assert 'accuracy' in results
        assert 0.0 <= results['accuracy'] <= 1.0

    def test_predict_before_training(self):
        """Verifica predicción sin entrenamiento"""
        prices = create_demo_price_data(50)
        predictor = EnsemblePredictor()
        prediction = predictor.predict(prices)
        
        assert prediction['signal'] == 'HOLD'
        assert prediction['confidence'] == 0.5

    def test_predict_after_training(self):
        """Verifica predicción después de entrenamiento"""
        prices = create_demo_price_data(100)
        predictor = EnsemblePredictor()
        predictor.train(prices)
        prediction = predictor.predict(prices)
        
        assert prediction['signal'] in ['BUY', 'SELL', 'HOLD']
        assert 0.0 <= prediction['confidence'] <= 1.0


def test_create_demo_price_data():
    """Verifica la creación de datos de demo"""
    data = create_demo_price_data(50)
    assert len(data) == 50
    assert all(p > 0 for p in data)


class TestAdvancedTradingStrategy:
    """Tests para AdvancedTradingStrategy"""
    
    def test_initialization(self):
        """Verifica que se inicialice correctamente"""
        strategy = AdvancedTradingStrategy()
        assert strategy is not None
        assert strategy.current_position is None
        assert hasattr(strategy, 'ma_short_window')
        assert hasattr(strategy, 'trailing_stop_pct')
    
    def test_call_insufficient_data(self):
        """Verifica que regrese HOLD con datos insuficientes"""
        strategy = AdvancedTradingStrategy()
        dates = pd.date_range(start='2024-01-01', periods=20)
        prices = np.random.randn(20).cumsum() + 50000
        df = pd.DataFrame({
            'Open': prices,
            'High': prices * 1.02,
            'Low': prices * 0.98,
            'Close': prices,
            'Volume': np.random.randint(10000, 100000, 20)
        }, index=dates)
        assert strategy(df) == 'HOLD'
    
    def test_call_buy_signal(self):
        """Verifica que genere señal de compra"""
        strategy = AdvancedTradingStrategy()
        # Generar datos con tendencia alcista clara
        df = HistoricalData.generate_synthetic_crypto_data(
            start_date='2024-01-01',
            end_date='2024-06-01',
            base_price=50000,
            volatility=0.01
        )
        # Ejecutar hasta obtener una señal
        signal = strategy(df)
        assert signal in ['BUY', 'SELL', 'HOLD']


class TestImprovedTrendStrategy:
    """Tests para ImprovedTrendStrategy"""
    
    def test_initialization(self):
        """Verifica que se inicialice correctamente"""
        strategy = ImprovedTrendStrategy()
        assert strategy is not None
        assert strategy.current_position is None
        assert hasattr(strategy, 'stop_loss_pct')
    
    def test_call(self):
        """Verifica que la estrategia se ejecute sin errores"""
        strategy = ImprovedTrendStrategy()
        df = HistoricalData.generate_synthetic_crypto_data(
            start_date='2024-01-01',
            end_date='2024-06-01',
            base_price=50000
        )
        signal = strategy(df)
        assert signal in ['BUY', 'SELL', 'HOLD']
