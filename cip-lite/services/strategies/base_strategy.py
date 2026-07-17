"""
Strategy ABC Interface - CIP Lite v2.0
Contrato común para todas las estrategias del sistema
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import pandas as pd
from datetime import datetime


@dataclass
class StrategySignal:
    """Señal de trading con metadata completa"""
    symbol: str
    signal: str  # BUY, SELL, HOLD, MARKET_MAKE
    confidence: float  # 0.0 - 1.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    strategy_name: str = "base"
    timestamp: datetime = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """
    Interfaz ABC base para todas las estrategias.
    Cualquier estrategia que herede de esta clase será compatible 
    con el orchestrator, backtesting y brain de CIP Lite.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Nombre único de la estrategia"""
        pass
    
    @property
    @abstractmethod
    def required_params(self) -> List[str]:
        """Lista de parámetros requeridos para la estrategia"""
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """Valida que los parámetros proporcionados son correctos"""
        required_keys = set(self.required_params)
        provided_keys = set(params.keys()) if params else set()
        return required_keys.issubset(provided_keys)
    
    @abstractmethod
    def __call__(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """
        Genera señal de trading basada en datos históricos.
        
        Args:
            df: DataFrame con columnas ['open', 'high', 'low', 'close', 'volume']
            symbol: Símbolo del activo (ej: 'BTC', 'ETH_USDT')
        
        Returns:
            StrategySignal con la decisión de trading o None si no aplica
        """
        pass
    
    def analyze_conditions(self, df: pd.DataFrame, signal: StrategySignal) -> Dict[str, Any]:
        """
        Analiza las condiciones que generaron la señal.
        Útil para entender por qué una operación fue ganadora o perdedora.
        
        Returns:
            Dict con condiciones de mercado al momento de la señal
        """
        return {
            "price": float(df['close'].iloc[-1]),
            "volume": float(df['volume'].iloc[-1]) if 'volume' in df.columns else 0,
            "volatility": float(df['close'].pct_change().rolling(20).std().iloc[-1]),
            "timestamp": signal.timestamp.isoformat() if signal.timestamp else datetime.now().isoformat()
        }


class StrategyRegistry:
    """Registro de estrategias disponibles"""
    
    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._metadata: Dict[str, Dict] = {}
    
    def register(self, strategy: BaseStrategy, category: str = "custom", description: str = ""):
        """Registra una estrategia nueva"""
        self._strategies[strategy.name] = strategy
        self._metadata[strategy.name] = {
            "category": category,
            "description": description,
            "params": strategy.required_params
        }
    
    def get(self, name: str) -> Optional[BaseStrategy]:
        """Obtiene una estrategia por nombre"""
        return self._strategies.get(name)
    
    def list_strategies(self) -> List[Dict[str, Any]]:
        """Lista todas las estrategias registradas"""
        return [
            {"name": name, **meta}
            for name, meta in self._metadata.items()
        ]
    
    def generate_all_signals(self, df: pd.DataFrame, symbol: str) -> List[StrategySignal]:
        """Genera señales de todas las estrategias"""
        signals = []
        for strategy in self._strategies.values():
            try:
                signal = strategy(df, symbol)
                if signal:
                    signals.append(signal)
            except Exception as e:
                # Log error pero continúa con otras estrategias
                continue
        return signals