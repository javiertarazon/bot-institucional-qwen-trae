"""
Tests for Portfolio Allocator
"""
import pytest
import pandas as pd
from services.execution.portfolio_optimizer import PortfolioAllocator


def test_initialization():
    """Test initialization"""
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    assert allocator.assets == ["BTC", "ETH"]


def test_generate_dummy_prices():
    """Test generate dummy prices"""
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    prices = allocator.generate_dummy_prices()
    assert isinstance(prices, pd.DataFrame)
    assert "BTC" in prices.columns
    assert "ETH" in prices.columns


def test_optimize_sharpe():
    """Test optimize with Sharpe ratio"""
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    prices = allocator.generate_dummy_prices()
    weights = allocator.optimize(prices, method="sharpe")
    assert isinstance(weights, dict)
    assert "BTC" in weights
    assert "ETH" in weights
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_optimize_min_vol():
    """Test optimize with min volatility"""
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    prices = allocator.generate_dummy_prices()
    weights = allocator.optimize(prices, method="min_vol")
    assert isinstance(weights, dict)
    assert "BTC" in weights
    assert "ETH" in weights
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_optimize_invalid_method(monkeypatch):
    """Test optimize with invalid method"""
    # Mock the PyPortfolioOpt imports
    mock_expected_returns = type('obj', (object,), {'mean_historical_return': lambda x: {}})
    mock_risk_models = type('obj', (object,), {'sample_cov': lambda x: {}})
    
    class MockEfficientFrontier:
        def __init__(self, *args, **kwargs):
            pass
        def max_sharpe(self):
            pass
        def min_volatility(self):
            pass
        def clean_weights(self):
            return {}
        def portfolio_performance(self, **kwargs):
            return (0, 0, 0)
    
    # Monkeypatch the modules in services.execution.portfolio_optimizer
    monkeypatch.setattr('services.execution.portfolio_optimizer.HAS_PYPO', True)
    # Directly assign the mocks to the module's namespace
    import services.execution.portfolio_optimizer as po_module
    po_module.expected_returns = mock_expected_returns
    po_module.risk_models = mock_risk_models
    po_module.EfficientFrontier = MockEfficientFrontier
    
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    prices = allocator.generate_dummy_prices()
    with pytest.raises(ValueError):
        allocator.optimize(prices, method="invalid")


def test_optimize_no_pypo(monkeypatch):
    """Test optimize when PyPortfolioOpt is not available"""
    monkeypatch.setattr("services.execution.portfolio_optimizer.HAS_PYPO", False)
    allocator = PortfolioAllocator(assets=["BTC", "ETH"])
    prices = allocator.generate_dummy_prices()
    weights = allocator.optimize(prices)
    assert isinstance(weights, dict)
    assert "BTC" in weights
    assert "ETH" in weights
    assert weights["BTC"] == 0.5
    assert weights["ETH"] == 0.5
