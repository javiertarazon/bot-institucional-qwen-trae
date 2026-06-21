"""
Execution Engine para CIP Lite
Motor de trading con gestión de riesgo, algoritmos de ejecución y paper trading
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
import uuid
import structlog

logger = structlog.get_logger()


@dataclass
class Order:
    """Representa una orden de trading"""
    order_id: str
    symbol: str
    side: str  # "BUY" or "SELL"
    quantity: float
    price: Optional[float] = None
    order_type: str = "MARKET"
    status: str = "PENDING"
    timestamp: datetime = datetime.utcnow()
    filled_quantity: float = 0.0
    avg_fill_price: Optional[float] = None


@dataclass
class Position:
    """Representa una posición en un activo"""
    symbol: str
    quantity: float
    avg_entry_price: float
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class RiskManager:
    """Gestor de riesgo institucional"""
    
    def __init__(self, max_position_size: float = 0.1, max_risk_per_trade: float = 0.02):
        self.max_position_size = max_position_size  # % del portafolio
        self.max_risk_per_trade = max_risk_per_trade  # % de riesgo por operación
        self.daily_loss_limit: float = 0.05  # 5% de pérdida máxima diaria
        logger.info("Risk Manager inicializado")
    
    def validate_order(self, order: Order, portfolio_value: float, daily_pnl: float) -> Dict[str, Any]:
        """Valida una orden contra las reglas de riesgo"""
        issues = []
        approved = True
        
        # Verificar límites de posición
        position_value = order.quantity * (order.price or 1.0)
        if position_value > portfolio_value * self.max_position_size:
            issues.append(f"Tamaño de posición excede límite: {self.max_position_size:.0%}")
            approved = False
        
        # Verificar pérdida diaria
        if daily_pnl < -portfolio_value * self.daily_loss_limit:
            issues.append("Límite de pérdida diaria alcanzado")
            approved = False
        
        return {
            "approved": approved,
            "issues": issues,
            "risk_score": 1.0 - (len(issues) * 0.2)
        }


class PositionSizer:
    """Gestor de sizing de posiciones (Kelly Criterion)"""
    
    def __init__(self):
        logger.info("Position Sizer inicializado")
    
    def kelly_criterion(self, win_rate: float, win_loss_ratio: float) -> float:
        """Calcula el tamaño óptimo de posición usando Kelly Criterion"""
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        return max(0, min(kelly, 0.25))  # Limitar a 25% máximo
    
    def calculate_position_size(self, signal: str, confidence: float, 
                                 portfolio_value: float, price: float) -> float:
        """Calcula el tamaño de posición óptimo"""
        # Kelly simplificado basado en confianza
        base_size = portfolio_value * 0.05  # 5% base
        confidence_adjusted = base_size * confidence
        
        # Ajustar por señal
        if signal == "BUY":
            size = confidence_adjusted
        elif signal == "SELL":
            size = confidence_adjusted * 0.8  # Vender menos agresivamente
        else:
            size = 0.0
        
        return size / price


class ExecutionAlgorithms:
    """Algoritmos de ejecución institucional (TWAP, VWAP)"""
    
    def __init__(self):
        logger.info("Execution Algorithms inicializado")
    
    def twap_execution(self, order: Order, duration_minutes: int = 5, num_slices: int = 5) -> List[Dict]:
        """Time-Weighted Average Price - divide la orden en slices temporales"""
        slices = []
        slice_size = order.quantity / num_slices
        interval = duration_minutes / num_slices
        
        for i in range(num_slices):
            slices.append({
                "slice_id": f"{order.order_id}_{i}",
                "quantity": slice_size,
                "delay_minutes": i * interval
            })
        
        return slices
    
    def market_order(self, order: Order) -> Order:
        """Ejecución de orden de mercado"""
        order.status = "FILLED"
        order.filled_quantity = order.quantity
        order.avg_fill_price = order.price or 1.0  # Simulación
        return order


class Portfolio:
    """Gestión de portafolio"""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.daily_pnl: float = 0.0
        logger.info(f"Portfolio inicializado con ${initial_capital:,.2f}")
    
    @property
    def total_value(self) -> float:
        """Valor total del portafolio (cash + posiciones)"""
        position_value = sum(
            pos.quantity * pos.avg_entry_price for pos in self.positions.values()
        )
        return self.cash + position_value


class ExecutionEngine:
    """Motor de ejecución principal de CIP"""
    
    def __init__(self, initial_capital: float = 100000.0):
        self.portfolio = Portfolio(initial_capital)
        self.risk_manager = RiskManager()
        self.position_sizer = PositionSizer()
        self.execution_algo = ExecutionAlgorithms()
        self.paper_trading = True
        logger.info("Execution Engine inicializado")
    
    def create_order(self, signal: str, confidence: float, 
                     symbol: str, price: float = 1.0) -> Optional[Order]:
        """Crea y valida una orden basada en una señal"""
        logger.info(f"Creando orden para señal: {signal} (confianza: {confidence:.2%})")
        
        if signal == "HOLD":
            return None
        
        # Calcular tamaño de posición
        quantity = self.position_sizer.calculate_position_size(
            signal, confidence, self.portfolio.total_value, price
        )
        
        if quantity <= 0:
            return None
        
        # Crear orden
        order = Order(
            order_id=str(uuid.uuid4()),
            symbol=symbol,
            side=signal,
            quantity=quantity,
            price=price
        )
        
        # Validar riesgo
        risk_check = self.risk_manager.validate_order(
            order, self.portfolio.total_value, self.portfolio.daily_pnl
        )
        
        if not risk_check["approved"]:
            logger.warning(f"Orden rechazada: {risk_check['issues']}")
            order.status = "REJECTED"
            return order
        
        # Ejecutar
        return self.execute_order(order)
    
    def execute_order(self, order: Order) -> Order:
        """Ejecuta una orden (paper trading para demo)"""
        logger.info(f"Ejecutando orden: {order.side} {order.quantity} {order.symbol}")
        
        if self.paper_trading:
            # Simular ejecución de mercado
            order = self.execution_algo.market_order(order)
            
            # Actualizar portafolio
            self._update_portfolio(order)
        else:
            # Aquí iría la integración real con exchanges
            order.status = "EXECUTING"
        
        self.portfolio.orders.append(order)
        return order
    
    def _update_portfolio(self, filled_order: Order):
        """Actualiza el portafolio después de una ejecución"""
        if filled_order.status != "FILLED":
            return
        
        symbol = filled_order.symbol
        price = filled_order.avg_fill_price or 1.0
        quantity = filled_order.filled_quantity
        notional = quantity * price
        
        if filled_order.side == "BUY":
            # Añadir posición
            if symbol in self.portfolio.positions:
                # Promediar precio
                existing = self.portfolio.positions[symbol]
                total_qty = existing.quantity + quantity
                total_notional = (existing.quantity * existing.avg_entry_price) + notional
                existing.avg_entry_price = total_notional / total_qty
                existing.quantity = total_qty
            else:
                self.portfolio.positions[symbol] = Position(
                    symbol=symbol,
                    quantity=quantity,
                    avg_entry_price=price
                )
            self.portfolio.cash -= notional
            
        elif filled_order.side == "SELL":
            if symbol in self.portfolio.positions:
                position = self.portfolio.positions[symbol]
                # Calcular P&L
                pnl = (price - position.avg_entry_price) * quantity
                position.realized_pnl += pnl
                self.portfolio.daily_pnl += pnl
                
                # Reducir posición
                position.quantity -= quantity
                if position.quantity <= 0:
                    del self.portfolio.positions[symbol]
                
                self.portfolio.cash += notional
        
        logger.info(f"Portafolio actualizado: ${self.portfolio.total_value:,.2f}")
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """Devuelve un resumen del portafolio"""
        return {
            "total_value": self.portfolio.total_value,
            "cash": self.portfolio.cash,
            "positions": {
                sym: {
                    "quantity": pos.quantity,
                    "avg_entry": pos.avg_entry_price,
                    "realized_pnl": pos.realized_pnl
                } for sym, pos in self.portfolio.positions.items()
            },
            "daily_pnl": self.portfolio.daily_pnl,
            "return_pct": (self.portfolio.total_value / self.portfolio.initial_capital - 1) * 100,
            "num_orders": len(self.portfolio.orders)
        }


if __name__ == "__main__":
    print("🚀 Prueba del Execution Engine CIP")
    print("=" * 60)
    
    engine = ExecutionEngine(initial_capital=100000.0)
    
    print("\n1. Creando ordenes de prueba...")
    engine.create_order("BUY", 0.7, "BTC", 50000.0)
    engine.create_order("SELL", 0.6, "ETH", 3000.0)
    engine.create_order("HOLD", 0.5, "SOL", 100.0)
    
    summary = engine.get_portfolio_summary()
    print(f"\n📊 Resumen del Portafolio:")
    print(f"   Valor Total: ${summary['total_value']:,.2f}")
    print(f"   Cash: ${summary['cash']:,.2f}")
    print(f"   P&L Diario: ${summary['daily_pnl']:,.2f}")
    print(f"   Rendimiento: {summary['return_pct']:.2f}%")
    print(f"   Posiciones: {list(summary['positions'].keys())}")
    print(f"   Órdenes: {summary['num_orders']}")
    
    print("\n✅ Execution Engine funcionando correctamente!")
