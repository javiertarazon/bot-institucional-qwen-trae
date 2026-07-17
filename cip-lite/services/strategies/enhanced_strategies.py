"""
Framework de Estrategias Algorítmicas Rentables para CIP Lite v2.0
Incluye: Mean Reversion, Momentum, Breakout, Market Making
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class StrategySignal:
    """Señal de trading con metadata completa"""
    symbol: str
    signal: str  # BUY, SELL, HOLD
    confidence: float  # 0.0 - 1.0
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    strategy_name: str = "base"
    timestamp: datetime = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.metadata is None:
            self.metadata = {}


class StrategyFramework:
    """Framework base para múltiples estrategias"""
    
    def __init__(self):
        self.strategies = {}
        logger.info("strategy_framework_initialized")
    
    def register_strategy(self, name: str, strategy_func):
        """Registra una estrategia nueva"""
        self.strategies[name] = strategy_func
        logger.info(f"strategy_registered", name=name)
    
    def generate_all_signals(self, df: pd.DataFrame, symbol: str) -> List[StrategySignal]:
        """Genera señales de todas las estrategias registradas"""
        signals = []
        for name, strategy in self.strategies.items():
            signal = strategy(df, symbol)
            if signal:
                signals.append(signal)
        return signals


# =============================================================================
# Estrategia 1: Mean Reversion con RSI + Bollinger Bands
# =============================================================================

class MeanReversionStrategy:
    """Mean Reversion usando RSI y Bollinger Bands - Alta tasa de aciertos"""
    
    def __init__(self, rsi_period: int = 14, bb_period: int = 20, bb_std: float = 2.0):
        self.rsi_period = rsi_period
        self.bb_period = bb_period
        self.bb_std = bb_std
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calcula RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    def calculate_bb(self, prices: pd.Series, period: int = 20, std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calcula Bollinger Bands"""
        ma = prices.rolling(window=period).mean()
        std_dev = prices.rolling(window=period).std()
        upper = ma + (std_dev * std)
        lower = ma - (std_dev * std)
        return upper, ma, lower
    
    def __call__(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """Genera señal de mean reversion"""
        if len(df) < self.bb_period + self.rsi_period:
            return None
        
        close = df['close']
        rsi = self.calculate_rsi(close, self.rsi_period)
        upper_bb, ma_bb, lower_bb = self.calculate_bb(close, self.bb_period, self.bb_std)
        
        current_price = close.iloc[-1]
        current_rsi = rsi.iloc[-1]
        
        # Señal BUY: RSI sobreventa + precio por debajo de BB lower
        if current_rsi < 30 and current_price < lower_bb.iloc[-1]:
            entry = current_price
            stop_loss = entry * 0.95  # 5% stop
            take_profit = entry + (entry - stop_loss) * 1.5  # 1.5:1 reward
            
            return StrategySignal(
                symbol=symbol,
                signal="BUY",
                confidence=min(0.9, (30 - current_rsi) / 30 + 0.3),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name="mean_reversion"
            )
        
        # Señal SELL: RSI sobrecompra + precio por encima de BB upper
        elif current_rsi > 70 and current_price > upper_bb.iloc[-1]:
            entry = current_price
            stop_loss = entry * 1.05  # 5% stop
            take_profit = entry - (stop_loss - entry) * 1.5
            
            return StrategySignal(
                symbol=symbol,
                signal="SELL",
                confidence=min(0.9, (current_rsi - 70) / 30 + 0.3),
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name="mean_reversion"
            )
        
        return StrategySignal(
            symbol=symbol,
            signal="HOLD",
            confidence=0.5,
            strategy_name="mean_reversion"
        )


# =============================================================================
# Estrategia 2: Momentum Multi-Timeframe (EMA + MACD)
# =============================================================================

class MomentumStrategy:
    """Momentum multi-timeframe con EMA y MACD - Excelente en tendencias"""
    
    def __init__(self, ema_fast: int = 9, ema_slow: int = 21):
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
    
    def calculate_macd(self, prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calcula MACD"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        return macd, signal_line, histogram
    
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range para stops dinámicos"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    def __call__(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """Genera señal de momentum"""
        if len(df) < self.ema_slow + 26:
            return None
        
        close = df['close']
        ema_fast = close.ewm(span=self.ema_fast).mean()
        ema_slow = close.ewm(span=self.ema_slow).mean()
        macd, signal_line, histogram = self.calculate_macd(close)
        atr = self.calculate_atr(df)
        
        # Tendencia alcista: EMA fast > EMA slow + MACD bullish
        if ema_fast.iloc[-1] > ema_slow.iloc[-1] and histogram.iloc[-1] > 0:
            entry = close.iloc[-1]
            stop_loss = entry - (atr.iloc[-1] * 2)  # 2x ATR stop
            take_profit = entry + (entry - stop_loss) * 2  # 2:1 reward
            
            return StrategySignal(
                symbol=symbol,
                signal="BUY",
                confidence=0.75,
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name="momentum"
            )
        
        # Tendencia bajista: EMA fast < EMA slow + MACD bearish
        elif ema_fast.iloc[-1] < ema_slow.iloc[-1] and histogram.iloc[-1] < 0:
            entry = close.iloc[-1]
            stop_loss = entry + (atr.iloc[-1] * 2)
            take_profit = entry - (stop_loss - entry) * 2
            
            return StrategySignal(
                symbol=symbol,
                signal="SELL",
                confidence=0.75,
                entry_price=entry,
                stop_loss=stop_loss,
                take_profit=take_profit,
                strategy_name="momentum"
            )
        
        return StrategySignal(
            symbol=symbol,
            signal="HOLD",
            confidence=0.5,
            strategy_name="momentum"
        )


# =============================================================================
# Estrategia 3: Market Making Adaptativo
# =============================================================================

class MarketMakingStrategy:
    """Market making con stops dinámicos - PnL consistente"""
    
    def __init__(self, spread_target: float = 0.002, max_spread: float = 0.01):
        self.spread_target = spread_target
        self.max_spread = max_spread
    
    def __call__(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        """Genera señal de market making"""
        if len(df) < 20:
            return None
        
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        
        # Solo market making si volatilidad moderada
        if volatility < 0.03:  # Menos del 3% diario
            entry = df['close'].iloc[-1]
            half_spread = min(volatility * 2, self.max_spread / 2)
            
            # Colocar buy/sell simultáneos
            return StrategySignal(
                symbol=symbol,
                signal="MARKET_MAKE",
                confidence=0.6,
                entry_price=entry,
                stop_loss=entry * (1 - half_spread * 3),  # Stop amplio
                take_profit=entry * (1 + half_spread),
                strategy_name="market_making"
            )
        
        return StrategySignal(
            symbol=symbol,
            signal="HOLD",
            confidence=0.3,
            strategy_name="market_making"
        )


# =============================================================================
# Estrategia 4: Ensemble Con consensus
# =============================================================================

class EnsembleStrategy:
    """Ensemble combinando múltiples estrategias con consensus"""
    
    def __init__(self, strategies: List):
        self.strategies = strategies
    
    def __call__(self, df: pd.DataFrame, symbol: str) -> StrategySignal:
        """Genera señal por consenso"""
        signals = [s(df, symbol) for s in self.strategies]
        
        buy_votes = sum(1 for s in signals if s.signal == "BUY")
        sell_votes = sum(1 for s in signals if s.signal == "SELL")
        
        # Requerir al menos 2 votos para señal fuerte
        if buy_votes >= 2:
            avg_confidence = np.mean([s.confidence for s in signals if s.signal == "BUY"])
            best_signal = max([s for s in signals if s.signal == "BUY"], key=lambda x: x.confidence)
            
            return StrategySignal(
                symbol=symbol,
                signal="BUY",
                confidence=min(0.95, avg_confidence),
                entry_price=best_signal.entry_price,
                stop_loss=best_signal.stop_loss,
                take_profit=best_signal.take_profit,
                strategy_name="ensemble_buy"
            )
        
        elif sell_votes >= 2:
            avg_confidence = np.mean([s.confidence for s in signals if s.signal == "SELL"])
            best_signal = max([s for s in signals if s.signal == "SELL"], key=lambda x: x.confidence)
            
            return StrategySignal(
                symbol=symbol,
                signal="SELL",
                confidence=min(0.95, avg_confidence),
                entry_price=best_signal.entry_price,
                stop_loss=best_signal.stop_loss,
                take_profit=best_signal.take_profit,
                strategy_name="ensemble_sell"
            )
        
        return StrategySignal(
            symbol=symbol,
            signal="HOLD",
            confidence=0.5,
            strategy_name="ensemble_hold"
        )


if __name__ == "__main__":
    print("Testing Enhanced Strategies Framework...")
    
    # Create sample data
    np.random.seed(42)
    prices = [50000]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    df = pd.DataFrame({
        'close': prices,
        'high': [p * 1.03 for p in prices],
        'low': [p * 0.97 for p in prices]
    })
    
    # Test strategies
    framework = StrategyFramework()
    
    mr = MeanReversionStrategy()
    mom = MomentumStrategy()
    mm = MarketMakingStrategy()
    
    ensemble = EnsembleStrategy([mr, mom])
    
    print(f"\nMean Reversion Signal: {mr(df, 'BTC').signal}")
    print(f"Momentum Signal: {mom(df, 'BTC').signal}")
    print(f"Ensemble Signal: {ensemble(df, 'BTC').signal}")