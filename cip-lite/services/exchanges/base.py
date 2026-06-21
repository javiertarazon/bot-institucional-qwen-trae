"""
Clase base abstracta para integración con exchanges
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LOSS_LIMIT = "stop_loss_limit"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    NEW = "new"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    PENDING_CANCEL = "pending_cancel"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class Order:
    id: str
    symbol: str
    type: OrderType
    side: OrderSide
    status: OrderStatus
    price: Optional[float] = None
    quantity: Optional[float] = None
    filled_quantity: Optional[float] = None
    quote_quantity: Optional[float] = None
    commission: Optional[float] = None
    commission_asset: Optional[str] = None
    timestamp: Optional[int] = None


@dataclass
class Balance:
    asset: str
    free: float
    locked: float
    total: float


@dataclass
class Ticker:
    symbol: str
    bid_price: float
    ask_price: float
    last_price: float
    volume_24h: float
    timestamp: int


class ExchangeBase(ABC):
    """Clase base abstracta para todos los exchanges"""

    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, **kwargs):
        self.api_key = api_key
        self.api_secret = api_secret
        self.name = self.__class__.__name__.replace("Exchange", "")
        logger.info(f"Inicializando exchange: {self.name}")

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Ticker:
        """Obtener información del ticker para un par"""
        pass

    @abstractmethod
    async def get_balance(self) -> Dict[str, Balance]:
        """Obtener balances de la cuenta"""
        pass

    @abstractmethod
    async def create_order(
        self,
        symbol: str,
        side: OrderSide,
        type: OrderType,
        quantity: float,
        price: Optional[float] = None
    ) -> Order:
        """Crear una orden en el exchange"""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancelar una orden"""
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Optional[Order]:
        """Obtener información de una orden"""
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        """Obtener órdenes abiertas"""
        pass
