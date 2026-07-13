"""
Tests unitarios para ClineBrain y ClineTradeExecutor
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.cline_brain import ClineBrain, ClineTradeExecutor, MarketAnalysis
from services.strategies.enhanced_strategies import StrategySignal


class TestMarketAnalysis:
    """Tests para MarketAnalysis dataclass"""
    
    def test_market_analysis_creation(self):
        """Verifica creación de MarketAnalysis"""
        analysis = MarketAnalysis(
            symbol="BTC",
            price=50000.0,
            trend="bullish",
            volatility=0.02,
            volume_profile="high",
            sentiment_score=0.5,
            support_levels=[49000],
            resistance_levels=[51000],
            timestamp=datetime.now()
        )
        
        assert analysis.symbol == "BTC"
        assert analysis.price == 50000.0
        assert analysis.trend == "bullish"
        assert analysis.volatility == 0.02


class TestClineBrain:
    """Tests para ClineBrain"""
    
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
            'low': [p * 0.97 for p in prices],
            'volume': np.random.randint(10000, 100000, 101)
        })
    
    @pytest.fixture
    def brain(self):
        """Fixture de ClineBrain"""
        return ClineBrain()
    
    def test_initialization(self, brain):
        """Verifica inicialización del cerebro"""
        assert brain.position_sizer is not None
        assert brain.strategies is not None
        assert "mean_reversion" in brain.strategies
        assert "momentum" in brain.strategies
    
    def test_analyze_market(self, brain, sample_df):
        """Verifica análisis de mercado"""
        analysis = brain.analyze_market(sample_df, "BTC", sentiment_score=0.3)
        
        assert isinstance(analysis, MarketAnalysis)
        assert analysis.symbol == "BTC"
        assert analysis.price > 0
        assert analysis.trend in ["bullish", "bearish", "neutral"]
        assert analysis.volatility > 0
        assert analysis.volume_profile in ["high", "normal", "low"]
    
    def test_analyze_market_insufficient_data(self, brain):
        """Verifica error con datos insuficientes"""
        short_df = pd.DataFrame({
            'close': [50000, 50100, 50200],
            'high': [50050, 50150, 50250],
            'low': [49950, 50050, 50150],
            'volume': [10000, 11000, 12000]
        })
        
        with pytest.raises(ValueError):
            brain.analyze_market(short_df, "BTC")
    
    def test_generate_trading_decision(self, brain, sample_df):
        """Verifica generación de decisión de trading"""
        signal = brain.generate_trading_decision(sample_df, "BTC", sentiment_score=0.3)
        
        assert isinstance(signal, StrategySignal)
        assert signal.symbol == "BTC"
        assert signal.signal in ["BUY", "SELL", "HOLD"]
        assert 0 <= signal.confidence <= 1
    
    def test_generate_trade_summary(self, brain, sample_df):
        """Verifica generación de resumen de operación"""
        signal = brain.generate_trading_decision(sample_df, "BTC")
        analysis = brain.analyze_market(sample_df, "BTC")
        
        summary = brain.generate_trade_summary(signal, analysis, sample_df)
        
        assert "Cline Brain" in summary
        assert signal.symbol in summary


class TestClineTradeExecutor:
    """Tests para ClineTradeExecutor"""
    
    @pytest.fixture
    def executor(self):
        """Fixture de executor"""
        return ClineTradeExecutor()
    
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
            'low': [p * 0.97 for p in prices],
            'volume': np.random.randint(10000, 100000, 101)
        })
    
    def test_initialization(self, executor):
        """Verifica inicialización del executor"""
        assert executor.brain is not None
        assert executor.risk_mgr is not None
    
    def test_execute_analysis_cycle(self, executor, sample_df):
        """Verifica ejecución de ciclo completo"""
        result = executor.execute_analysis_cycle(sample_df, "BTC", sentiment=0.0)
        
        assert "analysis" in result
        assert "signal" in result
        assert "risk_approved" in result
        assert "risk_issues" in result
        assert "summary" in result
    
    def test_check_risk_limits_normal(self, executor, sample_df):
        """Verifica límites de riesgo en condiciones normales"""
        signal = StrategySignal(
            symbol="BTC",
            signal="BUY",
            confidence=0.8,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0
        )
        analysis = MarketAnalysis(
            symbol="BTC",
            price=50000.0,
            trend="neutral",
            volatility=0.02,
            volume_profile="normal",
            sentiment_score=0.0,
            support_levels=[49000],
            resistance_levels=[51000],
            timestamp=datetime.now()
        )
        
        risk_check = executor._check_risk_limits(signal, analysis)
        
        assert "approved" in risk_check
        assert "issues" in risk_check
    
    def test_check_risk_limits_extreme_volatility(self, executor, sample_df):
        """Verifica límites de riesgo con volatilidad extrema"""
        signal = StrategySignal(
            symbol="BTC",
            signal="BUY",
            confidence=0.8,
            entry_price=50000.0,
            stop_loss=49000.0,
            take_profit=51000.0
        )
        analysis = MarketAnalysis(
            symbol="BTC",
            price=50000.0,
            trend="neutral",
            volatility=0.15,  # 15% - extreme
            volume_profile="normal",
            sentiment_score=0.0,
            support_levels=[49000],
            resistance_levels=[51000],
            timestamp=datetime.now()
        )
        
        risk_check = executor._check_risk_limits(signal, analysis)
        
        # Should have issues due to extreme volatility
        assert len(risk_check["issues"]) > 0 or risk_check["approved"] == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])