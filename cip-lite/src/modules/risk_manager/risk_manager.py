"""
Módulo de Gestión de Riesgo - v2.0
Sistema institucional con auto-ajuste al mercado
Extiende el DynamicRiskManager existente
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class RiskMetrics:
    """Métricas de riesgo en tiempo real"""
    value_at_risk: float           # VaR 95% en USD
    max_drawdown: float            # Drawdown actual
    daily_pnl: float               # P&L del día
    position_count: int            # Posiciones abiertas
    exposure_pct: float            # % del portfolio expuesto
    correlation_risk: float        # Riesgo de correlación
    consecutive_losses: int        # Pérdidas consecutivas
    current_regime: str            # Régimen de mercado actual


@dataclass
class RiskLimits:
    """Límites de riesgo configurables"""
    max_daily_var_pct: float = 0.02          # 2% VaR diario máximo
    max_drawdown_pct: float = 0.10           # 10% drawdown máximo
    max_consecutive_losses: int = 3          # 3 pérdidas consecutivas
    max_open_positions: int = 3              # Máximo 3 operaciones
    max_exposure_pct: float = 0.30           # 30% exposición máxima
    risk_per_trade_pct: float = 0.002        # 0.2% por trade ($1 en $500)
    circuit_breaker_pause_minutes: int = 60   # Pausa de 1h tras 3 pérdidas


class RiskManagerV2:
    """
    Gestor de riesgo institucional con auto-ajuste
    Mejora el DynamicRiskManager existente
    """
    
    def __init__(self, initial_capital: float = 500.0, 
                 limits: Optional[RiskLimits] = None):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_value = initial_capital
        self.limits = limits or RiskLimits()
        
        # Estado
        self.positions: Dict[str, dict] = {}
        self.daily_pnl: float = 0.0
        self.consecutive_losses: int = 0
        self.last_trade_result: Optional[str] = None
        self.circuit_breaker_active: bool = False
        self.circuit_breaker_until: Optional[datetime] = None
        
        # Historial
        self.trade_history: list = []
        self.daily_pnl_history: list = []
        
        logger.info(f"Risk Manager v2.0 inicializado | Capital: ${initial_capital:,.2f}")
    
    def calculate_position_size(self, signal_confidence: float, symbol: str,
                                 df: pd.DataFrame, price: float,
                                 regime: str = "sideways") -> Tuple[float, str]:
        """
        Calcula el tamaño de posición óptimo
        Returns: (size_in_usd, explanation)
        """
        # 1. Verificar circuit breaker
        if self.circuit_breaker_active:
            if datetime.now() < self.circuit_breaker_until:
                return 0.0, "CIRCUIT_BREAKER_ACTIVE"
            else:
                self.circuit_breaker_active = False
                self.consecutive_losses = 0
                logger.info("Circuit breaker desactivado - reanudando trading")
        
        # 2. Verificar límites globales
        if len(self.positions) >= self.limits.max_open_positions:
            return 0.0, "MAX_POSITIONS_REACHED"
        
        if self.positions.get(symbol):
            return 0.0, "POSITION_ALREADY_OPEN"
        
        # 3. Verificar drawdown
        current_dd = (self.peak_value - self.current_capital) / self.peak_value
        if current_dd > self.limits.max_drawdown_pct:
            return 0.0, f"MAX_DRAWDOWN_EXCEEDED: {current_dd:.1%}"
        
        # 4. Calcular riesgo base
        risk_usd = self.current_capital * self.limits.risk_per_trade_pct
        
        # 5. Ajuste por confianza de señal
        confidence_adj = min(1.0, signal_confidence * 1.5)
        risk_usd *= confidence_adj
        
        # 6. Ajuste por régimen de mercado
        regime_multiplier = self._get_regime_multiplier(regime)
        risk_usd *= regime_multiplier
        
        # 7. Ajuste por drawdown actual (reduce si hay DD)
        if current_dd > 0.05:  # 5% DD
            dd_factor = 1.0 - (current_dd / self.limits.max_drawdown_pct)
            risk_usd *= max(0.5, dd_factor)
        
        # 8. Ajuste por pérdidas consecutivas
        if self.consecutive_losses > 0:
            loss_factor = 1.0 - (self.consecutive_losses * 0.25)
            risk_usd *= max(0.3, loss_factor)
        
        # 9. Calcular tamaño final
        final_size = max(0.01, risk_usd)  # Mínimo $0.01
        
        explanation = f"Risk: ${risk_usd:.2f} | Conf: {signal_confidence:.2f} | Regime: {regime}"
        
        return final_size, explanation
    
    def _get_regime_multiplier(self, regime: str) -> float:
        """Multiplicador según régimen de mercado"""
        multipliers = {
            'trending_up': 1.2,
            'trending_down': 1.2,
            'sideways': 0.8,
            'volatile': 0.5,
            'MOMENTUM': 1.2,
            'LATERAL': 0.8
        }
        return multipliers.get(regime, 1.0)
    
    def calculate_stop_loss(self, entry_price: float, df: pd.DataFrame,
                            direction: str = "long", 
                            method: str = "atr") -> Tuple[float, str]:
        """
        Calcula stop loss dinámico
        Methods: 'atr', 'structure', 'fixed_pct'
        """
        if method == "atr":
            atr = self._calculate_atr(df)
            multiplier = 2.0
            
            if direction == "long":
                sl_price = entry_price - (atr * multiplier)
                explanation = f"ATR SL: {atr:.4f} × {multiplier} = {atr*multiplier:.4f}"
            else:
                sl_price = entry_price + (atr * multiplier)
                explanation = f"ATR SL: {atr:.4f} × {multiplier} = {atr*multiplier:.4f}"
        
        elif method == "structure":
            # Usar soporte/resistencia
            support = df['low'].rolling(20).min().iloc[-1]
            resistance = df['high'].rolling(20).max().iloc[-1]
            
            if direction == "long":
                sl_price = support * 0.999
                explanation = f"Structural SL: below support {support:.4f}"
            else:
                sl_price = resistance * 1.001
                explanation = f"Structural SL: above resistance {resistance:.4f}"
        
        else:  # fixed_pct
            pct = 0.01  # 1%
            if direction == "long":
                sl_price = entry_price * (1 - pct)
            else:
                sl_price = entry_price * (1 + pct)
            explanation = f"Fixed SL: {pct:.1%}"
        
        return sl_price, explanation
    
    def calculate_take_profit(self, entry_price: float, sl_price: float,
                              risk_reward_ratio: float = 1.5) -> Tuple[float, float]:
        """
        Calcula take profit basado en R:R
        Returns: (tp_price, rr_actual)
        """
        risk = abs(entry_price - sl_price)
        reward = risk * risk_reward_ratio
        
        if sl_price < entry_price:  # Long
            tp_price = entry_price + reward
        else:  # Short
            tp_price = entry_price - reward
        
        return tp_price, risk_reward_ratio
    
    def validate_trade(self, symbol: str, size: float, sl_price: float,
                       tp_price: float, direction: str) -> Tuple[bool, str]:
        """
        Valida si una operación cumple con los límites de riesgo
        """
        issues = []
        
        # 1. Verificar VaR diario
        var = self.value_at_risk()
        if var > self.current_capital * self.limits.max_daily_var_pct:
            issues.append(f"VaR excedido: ${var:.2f} (max: ${self.current_capital * self.limits.max_daily_var_pct:.2f})")
        
        # 2. Verificar drawdown
        current_dd = (self.peak_value - self.current_capital) / self.peak_value
        if current_dd > self.limits.max_drawdown_pct:
            issues.append(f"Drawdown máximo excedido: {current_dd:.1%}")
        
        # 3. Verificar exposición
        exposure = sum(p.get('value', 0) for p in self.positions.values())
        if exposure / self.current_capital > self.limits.max_exposure_pct:
            issues.append(f"Exposición máxima excedida: {exposure/self.current_capital:.1%}")
        
        # 4. Verificar R:R mínimo
        risk = abs(self.current_capital * self.limits.risk_per_trade_pct)
        reward = abs(tp_price - sl_price) * size
        rr = reward / risk if risk > 0 else 0
        if rr < 1.0:
            issues.append(f"R:R insuficiente: {rr:.2f} (mínimo: 1.0)")
        
        # 5. Circuit breaker
        if self.circuit_breaker_active:
            issues.append("Circuit breaker activo")
        
        approved = len(issues) == 0
        reason = "APPROVED" if approved else " | ".join(issues)
        
        return approved, reason
    
    def record_trade_result(self, symbol: str, pnl_usd: float, 
                           exit_price: float, exit_reason: str):
        """Registra el resultado de una operación"""
        # Actualizar capital
        self.current_capital += pnl_usd
        
        # Actualizar P&L diario
        self.daily_pnl += pnl_usd
        
        # Actualizar peak
        if self.current_capital > self.peak_value:
            self.peak_value = self.current_capital
        
        # Track consecutivas
        if pnl_usd < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Verificar circuit breaker
        if self.consecutive_losses >= self.limits.max_consecutive_losses:
            self._activate_circuit_breaker()
        
        # Remover posición
        if symbol in self.positions:
            del self.positions[symbol]
        
        # Guardar historial
        trade_record = {
            'timestamp': datetime.now(),
            'symbol': symbol,
            'pnl_usd': pnl_usd,
            'exit_price': exit_price,
            'exit_reason': exit_reason,
            'consecutive_losses': self.consecutive_losses,
            'capital_after': self.current_capital
        }
        self.trade_history.append(trade_record)
        
        logger.info(f"Trade cerrado: {symbol} | PnL: ${pnl_usd:+.2f} | "
                   f"Capital: ${self.current_capital:,.2f}")
    
    def _activate_circuit_breaker(self):
        """Activa pausa de seguridad tras pérdidas consecutivas"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + pd.Timedelta(
            minutes=self.limits.circuit_breaker_pause_minutes
        )
        logger.warning(f"🚨 CIRCUIT BREAKER ACTIVADO - Pausa de {self.limits.circuit_breaker_pause_minutes}min")
    
    def value_at_risk(self, confidence: float = 0.95) -> float:
        """Calcula VaR del portfolio"""
        if not self.positions:
            return 0.0
        
        # Método histórico simplificado
        portfolio_value = sum(
            p.get('size', 0) * p.get('entry_price', 0) 
            for p in self.positions.values()
        )
        
        # Volatilidad asumida 2% diaria para crypto
        daily_vol = 0.02
        z_score = 1.65 if confidence == 0.95 else 2.33
        
        var = portfolio_value * daily_vol * z_score
        return min(var, self.current_capital * 0.05)  # Max 5% del capital
    
    def get_metrics(self) -> RiskMetrics:
        """Obtiene métricas actuales de riesgo"""
        exposure = sum(
            p.get('size', 0) * p.get('entry_price', 0) 
            for p in self.positions.values()
        )
        
        current_dd = (self.peak_value - self.current_capital) / self.peak_value
        
        return RiskMetrics(
            value_at_risk=self.value_at_risk(),
            max_drawdown=current_dd,
            daily_pnl=self.daily_pnl,
            position_count=len(self.positions),
            exposure_pct=exposure / self.current_capital if self.current_capital > 0 else 0,
            correlation_risk=self._calculate_correlation_risk(),
            consecutive_losses=self.consecutive_losses,
            current_regime=self._detect_current_regime()
        )
    
    def _calculate_correlation_risk(self) -> float:
        """Calcula riesgo de correlación del portfolio"""
        if len(self.positions) <= 1:
            return 0.0
        
        # Simplificado: más activos = menor correlación
        diversity_bonus = min(1.0, len(self.positions) / 5.0)
        return 1.0 - diversity_bonus
    
    def _detect_current_regime(self) -> str:
        """Detecta régimen basado en performance reciente"""
        if len(self.trade_history) < 5:
            return "UNKNOWN"
        
        recent_trades = self.trade_history[-10:]
        wins = sum(1 for t in recent_trades if t['pnl_usd'] > 0)
        win_rate = wins / len(recent_trades)
        
        if win_rate > 0.6:
            return "FAVORABLE"
        elif win_rate < 0.3:
            return "ADVERSE"
        else:
            return "NEUTRAL"
    
    def update_position(self, symbol: str, side: str, size: float,
                       entry_price: float, stop_loss: float = None,
                       take_profit: float = None):
        """Registra nueva posición"""
        self.positions[symbol] = {
            'side': side,
            'size': size,
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'entry_time': datetime.now(),
            'value': size * entry_price
        }
        
        logger.info(f"Posición abierta: {symbol} | {side} | ${size:.2f} @ ${entry_price:.2f}")


# Función de conveniencia
def create_risk_manager(capital: float = 500.0) -> RiskManagerV2:
    """Factory para crear risk manager"""
    return RiskManagerV2(initial_capital=capital)


if __name__ == "__main__":
    print("Testing Risk Manager v2.0...")
    
    rm = RiskManagerV2(initial_capital=500.0)
    
    # Test position sizing
    df = pd.DataFrame({
        'close': [50000 * (1 + np.random.normal(0, 0.02)) for _ in range(100)],
        'high': [50000 * 1.02 for _ in range(100)],
        'low': [50000 * 0.98 for _ in range(100)]
    })
    
    size, explanation = rm.calculate_position_size(
        signal_confidence=0.8,
        symbol="EURUSD",
        df=df,
        price=1.0850,
        regime="MOMENTUM"
    )
    print(f"\nPosition Size: ${size:.2f}")
    print(f"Explanation: {explanation}")
    
    # Test stop loss
    sl, sl_explanation = rm.calculate_stop_loss(
        entry_price=1.0850,
        df=df,
        direction="long",
        method="atr"
    )
    print(f"\nStop Loss: {sl:.5f}")
    print(f"Explanation: {sl_explanation}")
    
    # Test validation
    approved, reason = rm.validate_trade(
        symbol="EURUSD",
        size=size,
        sl_price=sl,
        tp_price=1.0950,
        direction="long"
    )
    print(f"\nValidation: {'✅' if approved else '❌'} {reason}")
    
    print("\n✅ Risk Manager v2.0 funcionando correctamente")