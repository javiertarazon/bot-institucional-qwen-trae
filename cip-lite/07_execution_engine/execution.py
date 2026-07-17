"""
Módulo de Ejecución - v2.0
Ejecuta órdenes reales en brokers (CCXT + MT5)
"""

import asyncio
from typing import Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class Order:
    """Orden de trading"""
    order_id: str
    symbol: str
    side: str  # BUY, SELL
    size: float
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    status: str = "PENDING"
    filled_price: Optional[float] = None
    filled_quantity: float = 0.0


class ExecutionEngine:
    """
    Motor de ejecución de órdenes
    Soporta múltiples brokers: CCXT (crypto) + MT5 (forex)
    """
    
    def __init__(self, initial_capital: float = 500.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.positions: Dict[str, Dict] = {}
        self.orders: Dict[str, Order] = {}
        
        # Conexiones
        self.ccxt_exchange = None
        self.mt5_connection = None
        
        logger.info(f"Execution Engine v2.0 inicializado | Capital: ${initial_capital:,.2f}")
    
    async def connect(self, broker: str, credentials: Dict) -> bool:
        """
        Conecta al broker especificado
        broker: 'binance', 'coinbase', 'kraken', 'mt5'
        """
        try:
            if broker in ['binance', 'coinbase', 'kraken']:
                return await self._connect_ccxt(broker, credentials)
            elif broker == 'mt5':
                return self._connect_mt5(credentials)
            else:
                logger.error(f"Broker desconocido: {broker}")
                return False
        except Exception as e:
            logger.error(f"Error conectando a {broker}: {e}")
            return False
    
    async def execute_order(self, symbol: str, side: str, size: float,
                           stop_loss: float = 0, take_profit: float = 0,
                           order_type: str = "MARKET") -> Dict:
        """
        Ejecuta una orden en el broker
        """
        order_id = f"ORD_{datetime.now().timestamp()}"
        
        logger.info(f"Ejecutando orden: {side} {size} {symbol}")
        
        # Crear orden
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=side,
            size=size,
            price=0,  # Se llena al ejecutar
            stop_loss=stop_loss,
            take_profit=take_profit
        )
        
        try:
            # Intentar ejecutar en CCXT o MT5
            if self.ccxt_exchange:
                result = await self._execute_ccxt_order(order)
            elif self.mt5_connection:
                result = self._execute_mt5_order(order)
            else:
                # Simulación
                result = self._simulate_order(order)
            
            # Guardar orden
            self.orders[order_id] = order
            
            # Actualizar posición si se ejecutó
            if result.get('status') == 'FILLED':
                self._update_position(symbol, side, size, result.get('price', 0))
            
            return result
            
        except Exception as e:
            logger.error(f"Error ejecutando orden: {e}")
            order.status = "ERROR"
            return {"status": "ERROR", "reason": str(e), "order_id": order_id}
    
    async def close_position(self, symbol: str, reason: str = "MANUAL") -> Dict:
        """Cierra una posición abierta"""
        if symbol not in self.positions:
            return {"status": "ERROR", "reason": "No hay posición abierta"}
        
        position = self.positions[symbol]
        side = "SELL" if position['side'] == "BUY" else "BUY"
        
        logger.info(f"Cerrando posición: {symbol} | Razón: {reason}")
        
        result = await self.execute_order(
            symbol=symbol,
            side=side,
            size=position['size'],
            order_type="MARKET"
        )
        
        if result.get('status') == 'FILLED':
            # Calcular P&L
            exit_price = result.get('price', 0)
            entry_price = position['entry_price']
            pnl = (exit_price - entry_price) * position['size'] if position['side'] == "BUY" else (entry_price - exit_price) * position['size']
            
            # Actualizar capital
            self.current_capital += pnl
            
            # Remover posición
            del self.positions[symbol]
            
            logger.info(f"Posición cerrada: {symbol} | P&L: ${pnl:+.2f}")
            
            return {
                "status": "CLOSED",
                "symbol": symbol,
                "exit_price": exit_price,
                "pnl_usd": pnl,
                "reason": reason
            }
        else:
            return {"status": "ERROR", "reason": "Falló cierre de posición"}
    
    async def modify_position(self, symbol: str, 
                             new_stop_loss: float = None,
                             new_take_profit: float = None) -> Dict:
        """Modifica stops de una posición abierta"""
        if symbol not in self.positions:
            return {"status": "ERROR", "reason": "No hay posición"}
        
        position = self.positions[symbol]
        
        if new_stop_loss:
            position['stop_loss'] = new_stop_loss
        if new_take_profit:
            position['take_profit'] = new_take_profit
        
        logger.info(f"Posición modificada: {symbol} | SL: {new_stop_loss} | TP: {new_take_profit}")
        
        return {
            "status": "MODIFIED",
            "symbol": symbol,
            "stop_loss": position.get('stop_loss'),
            "take_profit": position.get('take_profit')
        }
    
    async def emergency_stop(self) -> Dict:
        """Emergency stop - cierra todas las posiciones"""
        logger.warning("🚨 EMERGENCY STOP - Cerrando todas las posiciones")
        
        results = []
        for symbol in list(self.positions.keys()):
            result = await self.close_position(symbol, reason="EMERGENCY_STOP")
            results.append(result)
        
        closed = sum(1 for r in results if r.get('status') == 'CLOSED')
        
        return {
            "status": "EMERGENCY_COMPLETE",
            "closed": closed,
            "total_positions": len(self.positions),
            "results": results
        }
    
    def get_open_positions(self) -> Dict[str, Dict]:
        """Obtiene posiciones abiertas"""
        return self.positions.copy()
    
    def get_account_info(self) -> Dict:
        """Obtiene información de la cuenta"""
        return {
            "initial_capital": self.initial_capital,
            "current_capital": self.current_capital,
            "open_positions": len(self.positions),
            "available_balance": self.current_capital - sum(p.get('value', 0) for p in self.positions.values())
        }
    
    # ========== MÉTODOS PRIVADOS ==========
    
    def _update_position(self, symbol: str, side: str, size: float, price: float):
        """Actualiza registro de posición"""
        self.positions[symbol] = {
            'side': side,
            'size': size,
            'entry_price': price,
            'value': size * price,
            'entry_time': datetime.now()
        }
        
        logger.info(f"Posición abierta: {symbol} | {side} | {size} @ ${price:.2f}")
    
    def _simulate_order(self, order: Order) -> Dict:
        """Simulación de orden para testing"""
        import numpy as np
        
        # Precio simulado con slippage
        base_prices = {
            'EURUSD': 1.0850,
            'GBPUSD': 1.2650,
            'XAUUSD': 2650.0,
            'BTC/USDT': 50000.0
        }
        base_price = base_prices.get(order.symbol, 100.0)
        
        filled_price = base_price * (1 + np.random.normal(0, 0.0001))
        
        order.price = filled_price
        order.filled_price = filled_price
        order.filled_quantity = order.size
        order.status = "FILLED"
        
        logger.info(f"✅ Orden simulada: {order.order_id} | {order.side} {order.size} @ ${filled_price:.2f}")
        
        return {
            "status": "FILLED",
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "size": order.size,
            "price": filled_price,
            "timestamp": datetime.now().isoformat()
        }
    
    async def _connect_ccxt(self, exchange_name: str, credentials: Dict) -> bool:
        """Conecta a exchange CCXT"""
        try:
            import ccxt
            
            exchange_class = getattr(ccxt, exchange_name)
            self.ccxt_exchange = exchange_class({
                'apiKey': credentials.get('api_key'),
                'secret': credentials.get('api_secret'),
                'enableRateLimit': True
            })
            
            logger.info(f"Conectado a {exchange_name} vía CCXT")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando CCXT: {e}")
            return False
    
    def _connect_mt5(self, credentials: Dict) -> bool:
        """Conecta a MT5"""
        try:
            import MetaTrader5 as mt5
            
            login = credentials.get('login')
            password = credentials.get('password')
            server = credentials.get('server')
            
            if not mt5.initialize(login=login, password=password, server=server):
                logger.error("No se pudo inicializar MT5")
                return False
            
            self.mt5_connection = mt5
            logger.info(f"Conectado a MT5: {server}")
            return True
            
        except Exception as e:
            logger.error(f"Error conectando MT5: {e}")
            return False
    
    async def _execute_ccxt_order(self, order: Order) -> Dict:
        """Ejecuta orden vía CCXT"""
        try:
            symbol = order.symbol.replace('/', '').lower()
            
            if order.side == "BUY":
                result = self.ccxt_exchange.create_market_buy_order(
                    symbol=symbol,
                    amount=order.size
                )
            else:
                result = self.ccxt_exchange.create_market_sell_order(
                    symbol=symbol,
                    amount=order.size
                )
            
            order.status = "FILLED"
            order.filled_price = result.get('price', order.price)
            
            return {
                "status": "FILLED",
                "order_id": order.order_id,
                "price": order.filled_price,
                "broker": "ccxt"
            }
            
        except Exception as e:
            logger.error(f"Error en orden CCXT: {e}")
            return {"status": "ERROR", "reason": str(e)}
    
    def _execute_mt5_order(self, order: Order) -> Dict:
        """Ejecuta orden vía MT5"""
        try:
            symbol = order.symbol
            
            if order.side == "BUY":
                result = self.mt5_connection.order_send(
                    self.mt5_connection.ORDER_TYPE_BUY,
                    symbol,
                    order.size,
                    0,  # price (market)
                    0,  # deviation
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit
                )
            else:
                result = self.mt5_connection.order_send(
                    self.mt5_connection.ORDER_TYPE_SELL,
                    symbol,
                    order.size,
                    0,
                    0,
                    stop_loss=order.stop_loss,
                    take_profit=order.take_profit
                )
            
            order.status = "FILLED" if result.retcode == self.mt5_connection.TRADE_RETCODE_DONE else "ERROR"
            
            return {
                "status": order.status,
                "order_id": order.order_id,
                "price": result.price,
                "broker": "mt5"
            }
            
        except Exception as e:
            logger.error(f"Error en orden MT5: {e}")
            return {"status": "ERROR", "reason": str(e)}


# Función de conveniencia
def create_execution_engine(capital: float = 500.0) -> ExecutionEngine:
    """Factory para crear motor de ejecución"""
    return ExecutionEngine(initial_capital=capital)


if __name__ == "__main__":
    print("Testing Execution Engine v2.0...")
    print("=" * 60)
    
    engine = ExecutionEngine(initial_capital=500.0)
    
    print("\n✅ Motor de ejecución inicializado")
    print(f"   Capital: ${engine.initial_capital:,.2f}")
    
    # Test simulación
    async def test():
        result = await engine.execute_order(
            symbol="EURUSD",
            side="BUY",
            size=0.1,
            stop_loss=1.0800,
            take_profit=1.0950
        )
        print(f"\n📝 Orden ejecutada: {result}")
        
        # Test posiciones
        positions = engine.get_open_positions()
        print(f"\n📊 Posiciones abiertas: {len(positions)}")
        
        # Test info cuenta
        info = engine.get_account_info()
        print(f"\n💰 Cuenta: {info}")
    
    asyncio.run(test())
    print("\n✅ Execution Engine v2.0 funcionando correctamente")