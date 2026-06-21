"""
Tests para módulos de ejecución de trading
"""
import pytest
import time
import uuid
from datetime import datetime
from services.execution.engine import (
    Order, Position, RiskManager, PositionSizer, ExecutionAlgorithms, Portfolio, ExecutionEngine
)
from services.execution.portfolio_optimizer import PortfolioAllocator
from services.metrics import LRUCache, MetricsCollector


class TestOrder:
    """Tests para la clase Order"""

    def test_initialization(self):
        """Verifica la inicialización de una orden"""
        order_id = str(uuid.uuid4())
        order = Order(
            order_id=order_id,
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0
        )
        
        assert order.order_id == order_id
        assert order.symbol == "BTC"
        assert order.side == "BUY"
        assert order.quantity == 0.1
        assert order.status == "PENDING"


class TestPosition:
    """Tests para la clase Position"""

    def test_initialization(self):
        """Verifica la inicialización de una posición"""
        position = Position(
            symbol="BTC",
            quantity=0.1,
            avg_entry_price=50000.0
        )
        
        assert position.symbol == "BTC"
        assert position.quantity == 0.1
        assert position.avg_entry_price == 50000.0
        assert position.unrealized_pnl == 0.0
        assert position.realized_pnl == 0.0


class TestRiskManager:
    """Tests para RiskManager"""

    def test_initialization(self):
        """Verifica la inicialización"""
        rm = RiskManager(max_position_size=0.15, max_risk_per_trade=0.03)
        assert rm is not None
        assert rm.max_position_size == 0.15

    def test_validate_order_approved(self):
        """Verifica la validación de una orden aprobada"""
        rm = RiskManager()
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0
        )
        result = rm.validate_order(order, portfolio_value=100000.0, daily_pnl=0.0)
        
        assert result["approved"] is True
        assert len(result["issues"]) == 0

    def test_validate_order_position_too_large(self):
        """Verifica la validación de una orden con posición excesiva"""
        rm = RiskManager(max_position_size=0.01)  # 1% límite
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,  # $5k position (10% of $50k initial)
            price=50000.0
        )
        result = rm.validate_order(order, portfolio_value=50000.0, daily_pnl=0.0)
        
        assert result["approved"] is False
        assert len(result["issues"]) > 0

    def test_validate_order_daily_loss_limit(self):
        """Verifica la validación de una orden cuando se alcanzó el límite de pérdida diaria"""
        rm = RiskManager()
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0
        )
        # Simular pérdida diaria de -10% de portafolio de $100k (límites es 5%)
        result = rm.validate_order(order, portfolio_value=100000.0, daily_pnl=-15000.0)
        
        assert result["approved"] is False
        assert "Límite de pérdida diaria alcanzado" in result["issues"]


class TestPositionSizer:
    """Tests para PositionSizer"""

    def test_initialization(self):
        """Verifica la inicialización"""
        sizer = PositionSizer()
        assert sizer is not None

    def test_kelly_criterion(self):
        """Verifica el cálculo del Kelly Criterion"""
        sizer = PositionSizer()
        kelly = sizer.kelly_criterion(win_rate=0.6, win_loss_ratio=2.0)
        
        assert 0.0 <= kelly <= 0.25

    def test_calculate_position_size_buy(self):
        """Verifica el cálculo del tamaño para una compra"""
        sizer = PositionSizer()
        size = sizer.calculate_position_size(
            signal="BUY",
            confidence=0.7,
            portfolio_value=100000.0,
            price=50000.0
        )
        
        assert size > 0.0

    def test_calculate_position_size_hold(self):
        """Verifica que retorne 0 para HOLD"""
        sizer = PositionSizer()
        size = sizer.calculate_position_size(
            signal="HOLD",
            confidence=0.5,
            portfolio_value=100000.0,
            price=50000.0
        )
        
        assert size == 0.0

    def test_calculate_position_size_sell(self):
        """Verifica el cálculo del tamaño para una venta"""
        sizer = PositionSizer()
        buy_size = sizer.calculate_position_size(
            signal="BUY",
            confidence=0.7,
            portfolio_value=100000.0,
            price=50000.0
        )
        sell_size = sizer.calculate_position_size(
            signal="SELL",
            confidence=0.7,
            portfolio_value=100000.0,
            price=50000.0
        )
        assert sell_size > 0.0
        assert sell_size == pytest.approx(buy_size * 0.8)  # SELL is 0.8 of BUY


class TestExecutionAlgorithms:
    """Tests para ExecutionAlgorithms"""

    def test_initialization(self):
        """Verifica la inicialización"""
        algo = ExecutionAlgorithms()
        assert algo is not None

    def test_twap_execution(self):
        """Verifica la ejecución TWAP"""
        algo = ExecutionAlgorithms()
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=1.0,
            price=50000.0
        )
        slices = algo.twap_execution(order)
        
        assert len(slices) > 0
        assert all("slice_id" in s for s in slices)
        assert all("quantity" in s for s in slices)

    def test_market_order(self):
        """Verifica la ejecución de orden de mercado"""
        algo = ExecutionAlgorithms()
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0
        )
        filled = algo.market_order(order)
        
        assert filled.status == "FILLED"
        assert filled.filled_quantity == 0.1


class TestPortfolio:
    """Tests para Portfolio"""

    def test_initialization(self):
        """Verifica la inicialización del portafolio"""
        portfolio = Portfolio(initial_capital=200000.0)
        
        assert portfolio.initial_capital == 200000.0
        assert portfolio.cash == 200000.0
        assert len(portfolio.positions) == 0
        assert portfolio.daily_pnl == 0.0

    def test_total_value_calculation(self):
        """Verifica el cálculo del valor total"""
        portfolio = Portfolio(initial_capital=100000.0)
        portfolio.positions["BTC"] = Position(
            symbol="BTC",
            quantity=0.5,
            avg_entry_price=50000.0
        )
        total = portfolio.total_value
        # Cash is still 100k (we didn't execute an order), position value 25k → total 125k
        assert total == 125000.0


class TestExecutionEngine:
    """Tests para ExecutionEngine"""

    def test_initialization(self):
        """Verifica la inicialización del motor de ejecución"""
        engine = ExecutionEngine(initial_capital=150000.0)
        
        assert engine is not None
        assert engine.portfolio.initial_capital == 150000.0
        assert engine.paper_trading is True

    def test_create_order_hold(self):
        """Verifica que no cree orden para señal HOLD"""
        engine = ExecutionEngine()
        order = engine.create_order("HOLD", 0.5, "BTC", 50000.0)
        
        assert order is None

    def test_create_and_execute_buy_order(self):
        """Verifica la creación y ejecución de una compra"""
        engine = ExecutionEngine(initial_capital=100000.0)
        order = engine.create_order("BUY", 0.7, "BTC", 50000.0)
        
        assert order is not None
        assert order.side == "BUY"
        assert order.status in ["FILLED", "REJECTED", "PENDING"]

    def test_get_portfolio_summary(self):
        """Verifica la obtención del resumen del portafolio"""
        engine = ExecutionEngine()
        summary = engine.get_portfolio_summary()
        
        assert "total_value" in summary
        assert "cash" in summary
        assert "positions" in summary
        assert "daily_pnl" in summary
        assert "return_pct" in summary
        assert "num_orders" in summary

    def test_create_order_zero_quantity(self):
        """Verifica que create_order retorne None cuando la cantidad es <= 0"""
        engine = ExecutionEngine()
        # Use confidence=0 to get quantity=0
        order = engine.create_order("BUY", 0.0, "BTC", 50000.0)
        
        assert order is None

    def test_create_order_risk_rejected(self):
        """Verifica que create_order retorne orden REJECTED cuando el riesgo es alto"""
        engine = ExecutionEngine()
        # Make risk manager's max position size very small
        engine.risk_manager.max_position_size = 0.001
        # Create a big order
        order = engine.create_order("BUY", 1.0, "BTC", 50000.0)
        
        assert order is not None
        assert order.status == "REJECTED"

    def test_execute_order_paper_trading_false(self):
        """Verifica que execute_order ponga status EXECUTING cuando paper_trading=False"""
        engine = ExecutionEngine()
        engine.paper_trading = False
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0
        )
        executed_order = engine.execute_order(order)
        
        assert executed_order.status == "EXECUTING"

    def test_update_portfolio_order_not_filled(self):
        """Verifica que _update_portfolio retorne temprano si la orden no está FILLED"""
        engine = ExecutionEngine()
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=0.1,
            price=50000.0,
            status="PENDING"
        )
        # Call _update_portfolio
        engine._update_portfolio(order)
        # Verify portfolio didn't change
        assert engine.portfolio.cash == engine.portfolio.initial_capital
        assert len(engine.portfolio.positions) == 0

    def test_update_portfolio_buy_existing_position(self):
        """Verifica que _update_portfolio promedie el precio de entrada cuando compra más de un activo existente"""
        engine = ExecutionEngine(initial_capital=200000.0)
        # First buy (create order directly)
        order1 = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=1.0,
            price=50000.0,
            status="FILLED",
            filled_quantity=1.0,
            avg_fill_price=50000.0
        )
        engine._update_portfolio(order1)
        engine.portfolio.orders.append(order1)
        # Second buy (create order directly)
        order2 = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=1.0,
            price=60000.0,
            status="FILLED",
            filled_quantity=1.0,
            avg_fill_price=60000.0
        )
        engine._update_portfolio(order2)
        engine.portfolio.orders.append(order2)
        
        # Verify position
        assert "BTC" in engine.portfolio.positions
        position = engine.portfolio.positions["BTC"]
        # (1*50k + 1*60k)/2 = 55k
        assert position.avg_entry_price == pytest.approx(55000.0)
        assert position.quantity == 2.0

    def test_update_portfolio_sell_position(self):
        """Verifica que _update_portfolio actualice correctamente al vender una posición"""
        engine = ExecutionEngine(initial_capital=200000.0)
        # First buy
        buy_order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=1.0,
            price=50000.0,
            status="FILLED",
            filled_quantity=1.0,
            avg_fill_price=50000.0
        )
        engine._update_portfolio(buy_order)
        engine.portfolio.orders.append(buy_order)
        # Now sell (create order directly)
        sell_order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="SELL",
            quantity=0.5,
            price=60000.0,
            status="FILLED",
            filled_quantity=0.5,
            avg_fill_price=60000.0
        )
        engine._update_portfolio(sell_order)
        engine.portfolio.orders.append(sell_order)
        
        assert sell_order.status == "FILLED"
        assert engine.portfolio.daily_pnl == pytest.approx(5000.0)  # 0.5 * (60k - 50k)
        assert engine.portfolio.positions["BTC"].quantity == pytest.approx(0.5)

    def test_update_portfolio_sell_entire_position(self):
        """Verifica que _update_portfolio borre la posición cuando se vende toda"""
        engine = ExecutionEngine(initial_capital=200000.0)
        # First buy
        buy_order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="BUY",
            quantity=1.0,
            price=50000.0,
            status="FILLED",
            filled_quantity=1.0,
            avg_fill_price=50000.0
        )
        engine._update_portfolio(buy_order)
        engine.portfolio.orders.append(buy_order)
        # Sell entire position (create order directly)
        sell_order = Order(
            order_id=str(uuid.uuid4()),
            symbol="BTC",
            side="SELL",
            quantity=1.0,
            price=60000.0,
            status="FILLED",
            filled_quantity=1.0,
            avg_fill_price=60000.0
        )
        engine._update_portfolio(sell_order)
        engine.portfolio.orders.append(sell_order)
        
        assert "BTC" not in engine.portfolio.positions


class TestPortfolioAllocator:
    """Tests para PortfolioAllocator"""

    def test_initialization(self):
        """Verifica la inicialización"""
        allocator = PortfolioAllocator(assets=['BTC', 'ETH', 'SOL'])
        assert allocator is not None
        assert len(allocator.assets) == 3

    def test_generate_dummy_prices(self):
        """Verifica la generación de precios dummy"""
        allocator = PortfolioAllocator()
        prices = allocator.generate_dummy_prices()
        
        assert len(prices) > 0
        assert all(asset in prices.columns for asset in allocator.assets)

    def test_optimize(self):
        """Verifica la optimización del portafolio"""
        allocator = PortfolioAllocator()
        prices = allocator.generate_dummy_prices()
        weights = allocator.optimize(prices)
        
        assert isinstance(weights, dict)
        assert len(weights) == len(allocator.assets)
        assert all(0.0 <= w <= 1.0 for w in weights.values())


class TestLRUCache:
    """Tests para LRUCache"""

    def test_initialization(self):
        """Verifica la inicialización"""
        cache = LRUCache(max_size=10, ttl_seconds=300)
        assert cache is not None
        assert cache.max_size == 10

    def test_set_and_get(self):
        """Verifica el almacenamiento y recuperación"""
        cache = LRUCache()
        cache.set("key1", "value1")
        value = cache.get("key1")
        
        assert value == "value1"

    def test_get_nonexistent(self):
        """Verifica que retorne None para clave no existente"""
        cache = LRUCache()
        value = cache.get("nonexistent")
        assert value is None

    def test_clear(self):
        """Verifica que limpie el caché"""
        cache = LRUCache()
        cache.set("key1", "value1")
        cache.clear()
        assert len(cache.cache) == 0


class TestMetricsCollector:
    """Tests para MetricsCollector"""

    def test_initialization(self):
        """Verifica la inicialización"""
        collector = MetricsCollector(prometheus_port=9999)
        assert collector is not None
        assert collector.cache_hits == 0
        assert collector.cache_misses == 0

    def test_record_cache_hit(self):
        """Verifica el registro de hit en caché"""
        collector = MetricsCollector(prometheus_port=10000)
        collector.record_cache_hit()
        assert collector.cache_hits == 1

    def test_record_cache_miss(self):
        """Verifica el registro de miss en caché"""
        collector = MetricsCollector(prometheus_port=10001)
        collector.record_cache_miss()
        assert collector.cache_misses == 1

    def test_collect_resource_metrics(self):
        """Verifica la colección de métricas de recursos"""
        collector = MetricsCollector(prometheus_port=10002)
        metrics = collector.collect_resource_metrics()
        
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "cache_hits" in metrics
        assert "cache_misses" in metrics
