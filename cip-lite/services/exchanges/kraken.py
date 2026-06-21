"""
Implementación de integración con Kraken
"""
import ccxt
from typing import Dict, List, Optional
from .base import (
    ExchangeBase, Order, Balance, Ticker,
    OrderType, OrderSide, OrderStatus
)
import structlog

logger = structlog.get_logger()


class KrakenExchange(ExchangeBase):
    """Clase para interactuar con Kraken"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, **kwargs):
        super().__init__(api_key, api_secret, **kwargs)
        self.client = ccxt.kraken({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            **kwargs
        })

    async def get_ticker(self, symbol: str) -> Ticker:
        """Obtener información del ticker para un par"""
        ticker = self.client.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            bid_price=float(ticker["bid"]),
            ask_price=float(ticker["ask"]),
            last_price=float(ticker["last"]),
            volume_24h=float(ticker["baseVolume"]),
            timestamp=int(ticker["timestamp"])
        )

    async def get_balance(self) -> Dict[str, Balance]:
        """Obtener balances de la cuenta"""
        balance = self.client.fetch_balance()
        balances = {}
        for asset, data in balance["total"].items():
            if data > 0:
                balances[asset] = Balance(
                    asset=asset,
                    free=float(balance["free"][asset]),
                    locked=float(balance["used"][asset]),
                    total=float(data)
                )
        return balances

    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: float,
        price: Optional[float] = None
    ) -> Order:
        """Crear una orden en el exchange"""
        order = self.client.create_order(
            symbol=symbol,
            type=type.value,
            side=side.value,
            amount=quantity,
            price=price
        )
        return Order(
            id=order["id"],
            symbol=symbol,
            type=OrderType(order["type"]),
            side=OrderSide(order["side"]),
            status=OrderStatus(order["status"]),
            price=float(order.get("price", 0)),
            quantity=float(order.get("amount", 0)),
            filled_quantity=float(order.get("filled", 0)),
            quote_quantity=float(order.get("cost", 0)),
            timestamp=int(order["timestamp"])
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancelar una orden"""
        try:
            self.client.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            logger.error(f"Error cancelando orden {order_id}: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Obtener información de una orden"""
        order = self.client.fetch_order(order_id, symbol)
        return Order(
            id=order["id"],
            symbol=symbol,
            type=OrderType(order["type"]),
            side=OrderSide(order["side"]),
            status=OrderStatus(order["status"]),
            price=float(order.get("price", 0)),
            quantity=float(order.get("amount", 0)),
            filled_quantity=float(order.get("filled", 0)),
            quote_quantity=float(order.get("cost", 0)),
            timestamp=int(order["timestamp"])
        )

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Obtener órdenes abiertas"""
        orders = self.client.fetch_open_orders(symbol)
        return [
            Order(
                id=o["id"],
                symbol=o["symbol"],
                type=OrderType(o["type"]),
                side=OrderSide(o["side"]),
                status=OrderStatus(o["status"]),
                price=float(o.get("price", 0)),
                quantity=float(o.get("amount", 0)),
                filled_quantity=float(o.get("filled", 0)),
                quote_quantity=float(o.get("cost", 0)),
                timestamp=int(o["timestamp"])
            )
            for o in orders
        ]
