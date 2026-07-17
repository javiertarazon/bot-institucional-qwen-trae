"""
Gestión de Riesgo Dinámica Avanzada para CIP Lite v2.0
Incluye: Stops ATR, Kelly variable, VaR diario, Correlation-aware sizing
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class RiskMetrics:
    """Métricas de riesgo actualizadas"""
    value_at_risk: float  # Maximum expected loss
    max_drawdown: float   # Current drawdown
    daily_pnl: float      # P&L acumulado del día
    position_count: int   # Número de posiciones abiertas
    exposure_pct: float   # % del portfolio expuesto
    correlation_risk: float  # Risk from correlated positions


class DynamicRiskManager:
    """Gestor de riesgo con gestión dinámica y adaptación al mercado"""
    
    def __init__(self, initial_capital: float = 100000.0, max_portfolio_risk: float = 0.02):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.max_portfolio_risk = max_portfolio_risk  # 2% max daily VaR
        self.positions: Dict[str, dict] = {}
        self.daily_pnl = 0.0
        self.peak_value = initial_capital
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}
        
    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ATR para stops dinámicos"""
        if len(df) < period:
            return df['close'].iloc[-1] * 0.02  # 2% default
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().iloc[-1]
    
    def calculate_dynamic_stop(self, entry_price: float, df: pd.DataFrame, 
                                direction: str = "long", multiplier: float = 2.0) -> float:
        """Stop loss dinámico basado en volatilidad (ATR)"""
        atr = self.calculate_atr(df)
        
        if direction == "long":
            return entry_price - (atr * multiplier)
        else:
            return entry_price + (atr * multiplier)
    
    def calculate_trailing_stop(self, current_price: float, entry_price: float,
                                df: pd.DataFrame, direction: str = "long") -> float:
        """Trailing stop que se ajusta con el profit"""
        atr = self.calculate_atr(df)
        
        if direction == "long":
            profit = current_price - entry_price
            trail_distance = max(atr * 2, profit * 0.5)  # Mínimo 2xATR o 50% del profit
            return current_price - trail_distance
        else:
            profit = entry_price - current_price
            trail_distance = max(atr * 2, profit * 0.5)
            return current_price + trail_distance
    
    def variable_kelly(self, win_rate: float, win_loss_ratio: float, 
                       volatility: float = 0.02, max_frac: float = 0.25) -> float:
        """
        Kelly Criterion variable según volatilidad del mercado
        Reduce el sizing en mercados más volátiles
        """
        # Kelly base
        kelly = win_rate - (1 - win_rate) / win_loss_ratio
        
        # Ajuste por volatilidad (reduce en mercados extremos)
        vol_factor = min(1.0, 1.0 / (1.0 + volatility * 10))
        
        return max(0.0, min(kelly * vol_factor, max_frac))
    
    def position_size(self, signal_confidence: float, symbol: str,
                       df: pd.DataFrame, price: float) -> float:
        """
        Sizing de posición dinámico considerando:
        - Confianza de la señal
        - Volatilidad del activo
        - Exposición actual del portfolio
        - Correlación con otras posiciones
        """
        # Calcular volatilidad reciente
        volatility = df['close'].pct_change().rolling(20).std().iloc[-1]
        
        # Kelly variable
        # Asumimos win_rate ~0.55, ratio ~1.5 basado en backtesting
        kelly_size = self.variable_kelly(0.55, 1.5, volatility)
        
        # Ajuste por confianza
        confidence_multiplier = min(1.0, signal_confidence * 2)
        
        # Factor de exposición (reduce si ya tenemos mucho riesgo)
        exposure_factor = max(0.3, 1.0 - (self.daily_pnl / self.current_capital))
        
        # Tamaño final como % del portfolio
        size_pct = kelly_size * confidence_multiplier * exposure_factor
        
        # Convertir a cantidad de activo
        return (self.current_capital * size_pct) / price
    
    def check_correlation_risk(self, new_symbol: str, new_position_size: float) -> bool:
        """
        Verifica si añadir esta posición incrementa el riesgo de correlación
        """
        # Simplified correlation check - in production use actual correlation data
        total_exposure = sum(self.positions.values()) * self.current_capital if self.positions else 0
        
        if total_exposure / self.current_capital > 0.3:  # Ya 30% expuesto
            logger.warning("high_correlation_risk", symbol=new_symbol, exposure_pct=total_exposure/self.current_capital)
            return False
        
        return True
    
    def value_at_risk(self, confidence: float = 0.95, horizon: int = 1) -> float:
        """
        Calcula VaR usando historico (más conservador)
        """
        if len(self.positions) == 0:
            return 0.0
        
        # Simplified VaR - en producción usar modelo de simulación Monte Carlo
        portfolio_vol = 0.0
        for symbol, position in self.positions.items():
            # Asumir volatilidad típica del 2% diario para crypto
            portfolio_vol += (position['size'] * position['entry_price'] * 0.02) ** 2
        
        portfolio_vol = np.sqrt(portfolio_vol / self.current_capital)
        
        # VaR a 95% confidence
        var = self.current_capital * portfolio_vol * 1.65
        
        return var
    
    def update_position(self, symbol: str, side: str, size: float, 
                        entry_price: float, stop_loss: float = None, 
                        take_profit: float = None):
        """Actualiza posición después de ejecución"""
        if side == "BUY":
            if symbol in self.positions:
                # Promediar entrada
                old = self.positions[symbol]
                total_cost = old['size'] * old['entry_price'] + size * entry_price
                self.positions[symbol] = {
                    'size': old['size'] + size,
                    'entry_price': total_cost / (old['size'] + size),
                    'stop_loss': stop_loss or old.get('stop_loss'),
                    'take_profit': take_profit or old.get('take_profit')
                }
            else:
                self.positions[symbol] = {
                    'size': size,
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit
                }
        
        # Actualizar capital
        if side == "BUY":
            self.current_capital -= size * entry_price * 1.001  # 0.1% commission
    
    def update_metrics(self) -> RiskMetrics:
        """Actualiza y retorna métricas de riesgo actuales"""
        exposure = sum(
            p['size'] * p['entry_price'] 
            for p in self.positions.values()
        )
        
        return RiskMetrics(
            value_at_risk=self.value_at_risk(),
            max_drawdown=(self.current_capital - self.peak_value) / self.peak_value,
            daily_pnl=self.daily_pnl,
            position_count=len(self.positions),
            exposure_pct=exposure / self.current_capital,
            correlation_risk=self._calculate_correlation_risk()
        )
    
    def _calculate_correlation_risk(self) -> float:
        """Risk score simplificado basado en diversificación"""
        if len(self.positions) <= 1:
            return 0.0
        
        # Más activos = menor correlación (simplificado)
        diversity_bonus = min(1.0, len(self.positions) / 10.0)
        return 1.0 - diversity_bonus


class AdaptivePositionSizer:
    """Ajuste de tamaño de posición según market regime"""
    
    def __init__(self):
        self.regimes = {
            'trending_up': {'multiplier': 1.2, 'max_size': 0.15},
            'trending_down': {'multiplier': 0.8, 'max_size': 0.10},
            'sideways': {'multiplier': 1.0, 'max_size': 0.08},
            'volatile': {'multiplier': 0.5, 'max_size': 0.05}
        }
    
    def detect_regime(self, df: pd.DataFrame) -> str:
        """Detecta el régimen del mercado"""
        if len(df) < 50:
            return 'sideways'
        
        # Calcular ADX para determinar tendencia
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(14).mean()
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        
        # Trend detection via price vs moving average
        ma50 = close.rolling(50).mean()
        price_vs_ma = (close.iloc[-1] / ma50.iloc[-1]) - 1
        
        if volatility > 0.05:
            return 'volatile'
        elif price_vs_ma > 0.05:
            return 'trending_up'
        elif price_vs_ma < -0.05:
            return 'trending_down'
        else:
            return 'sideways'
    
    def size_position(self, base_size: float, df: pd.DataFrame) -> float:
        """Ajuste de tamaño según régimen"""
        regime = self.detect_regime(df)
        config = self.regimes[regime]
        
        adjusted_size = base_size * config['multiplier']
        return min(adjusted_size, self.regimes[regime]['max_size'])


if __name__ == "__main__":
    print("Testing Dynamic Risk Manager...")
    
    # Sample data
    np.random.seed(42)
    prices = [50000]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    df = pd.DataFrame({
        'close': prices,
        'high': [p * 1.03 for p in prices],
        'low': [p * 0.97 for p in prices]
    })
    
    risk_mgr = DynamicRiskManager()
    sizer = AdaptivePositionSizer()
    
    # Test ATR
    atr = risk_mgr.calculate_atr(df)
    print(f"ATR (14): ${atr:.2f}")
    
    # Test dynamic stop
    stop = risk_mgr.calculate_dynamic_stop(50000, df, "long")
    print(f"Dynamic Stop (long): ${stop:.2f}")
    
    # Test regime detection
    regime = sizer.detect_regime(df)
    print(f"Market Regime: {regime}")
    
    # Test position size
    size = risk_mgr.position_size(0.8, "BTC", df, 50000)
    print(f"Position Size: {size:.6f} BTC (${size * 50000:.2f})")