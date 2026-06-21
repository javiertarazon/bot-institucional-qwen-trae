"""
Tests para el módulo de backtesting profesional
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from services.backtesting.engine import (
    BacktestConfig, HistoricalData, BacktestEngine, Strategy
)


class TestBacktestConfig:
    """Tests para BacktestConfig"""

    def test_initialization_defaults(self):
        """Verifica la inicialización con valores por defecto"""
        config = BacktestConfig()
        assert config.initial_capital == 100000.0
        assert config.commission_rate == 0.001
        assert config.slippage_pct == 0.0005
        assert config.max_position_pct == 0.1
        assert config.risk_per_trade_pct == 0.02
        assert config.lookback_window == 60


class TestHistoricalData:
    """Tests para HistoricalData"""

    def test_generate_synthetic_data(self):
        """Verifica la generación de datos históricos sintéticos"""
        start_date = "2024-01-01"
        end_date = "2024-06-01"
        
        df = HistoricalData.generate_synthetic_crypto_data(
            start_date=start_date,
            end_date=end_date,
            base_price=50000.0
        )
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert all(col in df.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume'])
        assert df.index[0] == pd.Timestamp(start_date)
        assert df.index[-1] == pd.Timestamp(end_date)


class TestBacktestEngine:
    """Tests para BacktestEngine"""

    @pytest.fixture
    def sample_data(self):
        """Fixture con datos de muestra"""
        return HistoricalData.generate_synthetic_crypto_data(
            start_date="2024-01-01",
            end_date="2024-03-01",
            base_price=50000.0
        )

    @pytest.fixture
    def sample_config(self):
        """Fixture con configuración de prueba"""
        return BacktestConfig(
            initial_capital=10000.0,
            commission_rate=0.001,
            slippage_pct=0.0005,
            max_position_pct=0.1,
            lookback_window=20
        )

    def test_initialization(self, sample_config):
        """Verifica la inicialización del motor"""
        engine = BacktestEngine(sample_config)
        assert engine.config == sample_config
        assert len(engine.equity_curve) == 0
        assert len(engine.trades) == 0
        assert engine.current_position is None

    def test_run_backtest(self, sample_data, sample_config):
        """Verifica la ejecución completa del backtesting"""
        engine = BacktestEngine(sample_config)
        results = engine.run(sample_data, Strategy.simple_trend_strategy)
        
        assert "equity_curve" in results
        assert "total_trades" in results
        assert "win_rate" in results
        assert "total_return" in results
        assert "sharpe_ratio" in results
        assert "max_drawdown" in results
        assert len(results["equity_curve"]) > 0

    def test_calculate_current_equity(self, sample_data, sample_config):
        """Verifica el cálculo de equity"""
        engine = BacktestEngine(sample_config)
        
        # Ejecutar un paso para tener datos
        engine.run(sample_data, Strategy.simple_trend_strategy)
        final_equity = engine.equity_curve[-1]
        
        assert final_equity > 0
        # El equity debería ser cercano al inicial (o diferente dependiendo de la estrategia)
        assert isinstance(final_equity, float)

    def test_calculate_results(self, sample_data, sample_config):
        """Verifica el cálculo de métricas"""
        engine = BacktestEngine(sample_config)
        results = engine.run(sample_data, Strategy.simple_trend_strategy)
        
        # Verificar que las métricas son valores numéricos válidos
        assert 0.0 <= results["win_rate"] <= 1.0
        assert -1.0 <= results["max_drawdown"] <= 0.0
        assert isinstance(results["total_trades"], int)
        assert isinstance(results["winning_trades"], int)
        assert isinstance(results["losing_trades"], int)


class TestStrategy:
    """Tests para Strategy"""

    @pytest.fixture
    def sample_data(self):
        """Fixture con datos de muestra"""
        return HistoricalData.generate_synthetic_crypto_data(
            start_date="2024-01-01",
            end_date="2024-03-01",
            base_price=50000.0
        )

    def test_simple_trend_strategy_hold_short_data(self):
        """Verifica que la estrategia retorne HOLD con datos insuficientes"""
        # Crear datos muy cortos
        short_data = pd.DataFrame({
            'Close': [50000, 50500, 51000]
        }, index=pd.date_range("2024-01-01", periods=3))
        
        signal = Strategy.simple_trend_strategy(short_data)
        assert signal == 'HOLD'

    def test_simple_trend_strategy_returns_valid_signal(self, sample_data):
        """Verifica que la estrategia retorne una señal válida"""
        signal = Strategy.simple_trend_strategy(sample_data)
        assert signal in ['BUY', 'SELL', 'HOLD']
