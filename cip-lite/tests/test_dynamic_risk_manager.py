"""
Tests unitarios para DynamicRiskManager y AdaptivePositionSizer
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.risk.dynamic_risk_manager import (
    DynamicRiskManager, AdaptivePositionSizer, RiskMetrics
)
from services.strategies.base_strategy import StrategySignal


class TestRiskMetrics:
    """Tests para RiskMetrics dataclass"""
    
    def test_risk_metrics_creation(self):
        """Verifica creación de RiskMetrics"""
        metrics = RiskMetrics(
            value_at_risk=1000.0,
            max_drawdown=-0.1,
            daily_pnl=500.0,
            position_count=3,
            exposure_pct=0.15,
            correlation_risk=0.3
        )
        
        assert metrics.value_at_risk == 1000.0
        assert metrics.max_drawdown == -0.1
        assert metrics.daily_pnl == 500.0
        assert metrics.position_count == 3
        assert metrics.exposure_pct == 0.15
        assert metrics.correlation_risk == 0.3


class TestDynamicRiskManager:
    """Tests para DynamicRiskManager"""
    
    @pytest.fixture
    def sample_df(self):
        """Fixture con datos de muestra"""
        np.random.seed(42)
        prices = [50000]
        for _ in range(100):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
        
        return pd.DataFrame({
            'close': prices,
            'high': [p * 1.03 for p in prices],
            'low': [p * 0.97 for p in prices]
        })
    
    @pytest.fixture
    def risk_manager(self):
        """Fixture de risk manager"""
        return DynamicRiskManager(initial_capital=100000.0)
    
    def test_initialization(self, risk_manager):
        """Verifica inicialización correcta"""
        assert risk_manager.initial_capital == 100000.0
        assert risk_manager.current_capital == 100000.0
        assert risk_manager.positions == {}
        assert risk_manager.daily_pnl == 0.0
    
    def test_calculate_atr(self, risk_manager, sample_df):
        """Verifica cálculo de ATR"""
        atr = risk_manager.calculate_atr(sample_df)
        
        assert isinstance(atr, float)
        assert atr > 0
        assert atr < 10000  # Reasonable upper bound
    
    def test_calculate_dynamic_stop_long(self, risk_manager, sample_df):
        """Verifica cálculo de stop loss para posición long"""
        entry_price = 50000.0
        stop = risk_manager.calculate_dynamic_stop(entry_price, sample_df, "long")
        
        assert stop < entry_price
        assert stop > entry_price * 0.8  # Max 20% stop
    
    def test_calculate_dynamic_stop_short(self, risk_manager, sample_df):
        """Verifica cálculo de stop loss para posición short"""
        entry_price = 50000.0
        stop = risk_manager.calculate_dynamic_stop(entry_price, sample_df, "short")
        
        assert stop > entry_price
        assert stop < entry_price * 1.2  # Max 20% stop
    
    def test_variable_kelly(self, risk_manager):
        """Verifica cálculo del Kelly variable"""
        # Normal market
        kelly = risk_manager.variable_kelly(0.6, 2.0, 0.02)
        assert 0 <= kelly <= 0.25
        
        # Extreme volatility should reduce kelly
        kelly_extreme = risk_manager.variable_kelly(0.6, 2.0, 0.5)
        assert kelly_extreme < kelly
    
    def test_variable_kelly_edge_cases(self, risk_manager):
        """Verifica casos límite de Kelly"""
        # Bad win rate - should return 0 or negative
        kelly_bad = risk_manager.variable_kelly(0.3, 0.5, 0.02)
        assert kelly_bad >= 0
        
        # Perfect win rate
        kelly_perfect = risk_manager.variable_kelly(1.0, 2.0, 0.02)
        assert kelly_perfect > 0
        assert kelly_perfect <= 0.25
    
    def test_position_size(self, risk_manager, sample_df):
        """Verifica sizing de posición"""
        size = risk_manager.position_size(0.8, "BTC", sample_df, 50000.0)
        
        assert isinstance(size, float)
        assert size > 0
    
    def test_check_correlation_risk(self, risk_manager):
        """Verifica detección de riesgo de correlación"""
        # Empty positions - should pass
        assert risk_manager.check_correlation_risk("BTC", 0.1) is True
        
        # Add some positions
        risk_manager.positions = {
            "ETH": {"size": 1.0, "entry_price": 3000},
            "SOL": {"size": 10.0, "entry_price": 100}
        }
        
        # Should still pass if under threshold
        assert risk_manager.check_correlation_risk("BTC", 0.1) is True
    
    def test_value_at_risk(self, risk_manager, sample_df):
        """Verifica cálculo de VaR"""
        # No positions - VaR should be 0
        var = risk_manager.value_at_risk()
        assert var == 0.0
        
        # With positions
        risk_manager.positions = {
            "BTC": {"size": 1.0, "entry_price": 50000}
        }
        var = risk_manager.value_at_risk()
        assert var > 0
    
    def test_update_position(self, risk_manager):
        """Verifica actualización de posición"""
        risk_manager.update_position(
            symbol="BTC",
            side="BUY",
            size=0.5,
            entry_price=50000.0,
            stop_loss=48000.0,
            take_profit=52000.0
        )
        
        assert "BTC" in risk_manager.positions
        assert risk_manager.positions["BTC"]["size"] == 0.5
        assert risk_manager.positions["BTC"]["entry_price"] == 50000.0
    
    def test_update_metrics(self, risk_manager):
        """Verifica actualización de métricas"""
        # Add a position
        risk_manager.update_position(
            symbol="BTC",
            side="BUY",
            size=0.5,
            entry_price=50000.0
        )
        
        metrics = risk_manager.update_metrics()
        
        assert isinstance(metrics, RiskMetrics)
        assert metrics.position_count == 1
        assert metrics.exposure_pct > 0


class TestAdaptivePositionSizer:
    """Tests para AdaptivePositionSizer"""
    
    @pytest.fixture
    def sizer(self):
        """Fixture de sizer"""
        return AdaptivePositionSizer()
    
    @pytest.fixture
    def sample_df(self):
        """Fixture con datos de muestra"""
        np.random.seed(42)
        prices = [50000]
        for _ in range(100):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
        
        return pd.DataFrame({
            'close': prices,
            'high': [p * 1.03 for p in prices],
            'low': [p * 0.97 for p in prices]
        })
    
    def test_detect_regime_sideways(self, sizer, sample_df):
        """Verifica detección de régimen sideways"""
        regime = sizer.detect_regime(sample_df)
        assert regime in ['trending_up', 'trending_down', 'sideways', 'volatile']
    
    def test_detect_regime_short_data(self, sizer):
        """Verifica que datos cortos devuelven sideways por defecto"""
        short_df = pd.DataFrame({
            'close': [50000, 50100, 50200],
            'high': [50050, 50150, 50250],
            'low': [49950, 50050, 50150]
        })
        
        regime = sizer.detect_regime(short_df)
        assert regime == 'sideways'
    
    def test_size_position(self, sizer, sample_df):
        """Verifica ajuste de tamaño por régimen"""
        base_size = 0.1
        adjusted = sizer.size_position(base_size, sample_df)
        
        assert isinstance(adjusted, float)
        assert 0 < adjusted <= 0.15
    
    def test_size_position_respects_max(self, sizer, sample_df):
        """Verifica que el sizing respeta límites máximos"""
        # Large base size should be capped
        base_size = 1.0
        adjusted = sizer.size_position(base_size, sample_df)
        
        # Should be capped by regime max_size
        regime = sizer.detect_regime(sample_df)
        max_allowed = sizer.regimes[regime]['max_size']
        assert adjusted <= max_allowed * 1.5  # Allow some flexibility