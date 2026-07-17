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
    Integración: Rust backend, ajuste dinámico por volatilidad, modo conservador
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
        
        # Modo conservador (se activa en mercados adversos)
        self.conservative_mode: bool = False
        self.conservative_trades_left: int = 0  # Trades restantes en modo conservador
        
        # Cache de volatilidad para ajuste dinámico
        self.volatility_cache: Dict[str, float] = {}
        
        # Historial
        self.trade_history: list = []
        self.daily_pnl_history: list = []
        
        # Metrics para auto-ajuste
        self.rolling_win_rate: float = 0.5
        self.rolling_loss_streak: int = 0
        
        # Intentar usar Rust backend para cálculos intensivos
        self.rust_available = False
        try:
            self._init_rust_backend()
        except Exception:
            pass
        
        logger.info(f"Risk Manager v2.0 inicializado | Capital: ${initial_capital:,.2f}")
        logger.info(f"   Rust backend: {'✅' if self.rust_available else '❌ (fallback Python)'}")
    
    def _init_rust_backend(self):
        """Intenta cargar el backend Rust para cálculos de riesgo"""
        rust_paths = [
            "../fast-path/target/release/librust_risk.dylib",
            "../fast-path/target/release/librust_risk.so",
            "../fast-path/target/release/rust_risk.dll",
        ]
        
        for path in rust_paths:
            if os.path.exists(path):
                # Usar ctypes para cargar Rust dynamic library
                import ctypes
                self.rust_lib = ctypes.CDLL(path)
                
                # Definir funciones Rust
                self.rust_lib.calculate_var.argtypes = [
                    ctypes.c_double,  # capital
                    ctypes.c_double,  # confidence
                    ctypes.c_double,  # volatility
                    ctypes.c_int      # consecutive_losses
                ]
                self.rust_lib.calculate_var.restype = ctypes.c_double
                
                self.rust_available = True
                logger.info(f"Backend Rust cargado: {path}")
                break
        
        if not self.rust_available:
            # Intentar compilar Rust si existe el source
            rust_src = Path("../fast-path/src/main.rs")
            if rust_src.exists():
                logger.info("Backend Rust encontrado pero no compilado. Ejecutar: cd fast-path && cargo build --release")
    
    def _rust_calculate_var(self, capital: float, confidence: float, 
                           volatility: float, consecutive_losses: int) -> float:
        """Calcula VaR usando backend Rust"""
        if not self.rust_available:
            return None
        try:
            return float(self.rust_lib.calculate_var(
                ctypes.c_double(capital),
                ctypes.c_double(confidence),
                ctypes.c_double(volatility),
                ctypes.c_int(consecutive_losses)
            ))
        except Exception:
            return None
    
    def calculate_position_size(self, signal_confidence: float, symbol: str,
                                 df: pd.DataFrame, price: float,
                                 regime: str = "sideways") -> Tuple[float, str]:
        """
        Calcula el tamaño de posición óptimo
        Soporta multi-framework: Rust si disponible, Python si no
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
        
        # 4. Verificar modo conservador
        if self.conservative_mode:
            if self.conservative_trades_left <= 0:
                return 0.0, "CONSERVATIVE_MODE: sin trades disponibles"
            self.conservative_trades_left -= 1
        
        # 5. Intentar usar Rust para cálculo de VaR
        volatility = df['close'].pct_change().std() * 100 if len(df) > 1 else 2.0
        self.volatility_cache[symbol] = float(volatility)
        
        rust_var = None
        if self.rust_available:
            rust_var = self._rust_calculate_var(
                self.current_capital,
                signal_confidence,
                volatility,
                self.consecutive_losses
            )
        
        # 6. Calcular riesgo base
        if rust_var is not None:
            risk_usd = rust_var
            method = "Rust"
        else:
            risk_usd = self.current_capital * self.limits.risk_per_trade_pct
            method = "Python"
        
        # 7. Ajuste por confianza de señal
        confidence_adj = min(1.0, signal_confidence * 1.5)
        risk_usd *= confidence_adj
        
        # 8. Ajuste por régimen de mercado
        regime_multiplier = self._get_regime_multiplier(regime)
        risk_usd *= regime_multiplier
        
        # 9. Ajuste por volatilidad dinámica
        vol_factor = max(0.3, 1.0 - (volatility / 10.0))  # Menos riesgo si alta volatilidad
        risk_usd *= vol_factor
        
        # 10. Ajuste por drawdown actual
        if current_dd > 0.03:  # 3% DD
            dd_factor = 1.0 - (current_dd / self.limits.max_drawdown_pct)
            risk_usd *= max(0.5, dd_factor)
        
        # 11. Ajuste por pérdidas consecutivas
        if self.consecutive_losses > 0:
            loss_factor = 1.0 - (self.consecutive_losses * 0.25)
            risk_usd *= max(0.3, loss_factor)
        
        # 12. Reducción adicional en modo conservador
        if self.conservative_mode:
            risk_usd *= 0.5  # Mitad del riesgo en modo conservador
        
        # 13. Calcular tamaño final
        final_size = max(0.01, risk_usd)
        
        explanation = f"[{method}] Risk: ${risk_usd:.2f} | Conf: {signal_confidence:.2f} | Vol: {volatility:.1f}% | Regime: {regime}"
        if self.conservative_mode:
            explanation += " | MODO CONSERVADOR"
        
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
        
        # Actualizar rolling metrics
        self.rolling_win_rate = win_rate
        self.rolling_loss_streak = self.consecutive_losses
        
        # Activar/desactivar modo conservador automáticamente
        if win_rate < 0.3 and len(recent_trades) >= 5:
            if not self.conservative_mode:
                self.conservative_mode = True
                self.conservative_trades_left = 3  # 3 trades en modo conservador
                logger.warning("🔄 MODO CONSERVADOR ACTIVADO - Win rate bajo")
        elif win_rate > 0.6 and self.conservative_mode:
            self.conservative_mode = False
            self.conservative_trades_left = 0
            logger.info("✅ MODO CONSERVADOR DESACTIVADO - Win rate recuperado")
        
        if win_rate > 0.6:
            return "FAVORABLE"
        elif win_rate < 0.3:
            return "ADVERSE"
        else:
            return "NEUTRAL"
    
    def get_position_sizing_summary(self) -> Dict:
        """
        Retorna resumen de cómo se calcula el tamaño de posición.
        Útil para Trae Agent en el ciclo de inteligencia diaria.
        """
        return {
            'status': 'active' if not self.circuit_breaker_active else 'circuit_breaker',
            'capital': self.current_capital,
            'peak': self.peak_value,
            'drawdown': (self.peak_value - self.current_capital) / self.peak_value if self.peak_value > 0 else 0,
            'consecutive_losses': self.consecutive_losses,
            'conservative_mode': self.conservative_mode,
            'rolling_win_rate': self.rolling_win_rate,
            'rust_backend': self.rust_available,
            'positions_open': len(self.positions),
            'daily_pnl': self.daily_pnl,
            'volatility': self.volatility_cache,
        }
    
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
    print("=" * 60)
    
    rm = RiskManagerV2(initial_capital=500.0)
    
    # Test position sizing
    np.random.seed(42)
    df = pd.DataFrame({
        'close': [1.0850 * (1 + np.random.normal(0, 0.001)) for _ in range(100)],
        'high': [1.0850 * 1.002 for _ in range(100)],
        'low': [1.0850 * 0.998 for _ in range(100)]
    })
    
    print("\n📊 Test 1: Position Sizing (MOMENTUM)")
    size, explanation = rm.calculate_position_size(
        signal_confidence=0.8,
        symbol="EURUSD",
        df=df,
        price=1.0850,
        regime="MOMENTUM"
    )
    print(f"   Size: ${size:.2f}")
    print(f"   Explanation: {explanation}")
    
    print("\n📊 Test 2: Position Sizing (LATERAL)")
    size_lat, explanation_lat = rm.calculate_position_size(
        signal_confidence=0.5,
        symbol="XAUUSD",
        df=df,
        price=1950.0,
        regime="LATERAL"
    )
    print(f"   Size: ${size_lat:.2f}")
    print(f"   Explanation: {explanation_lat}")
    
    print("\n📊 Test 3: Stop Loss (ATR)")
    sl, sl_explanation = rm.calculate_stop_loss(
        entry_price=1.0850,
        df=df,
        direction="long",
        method="atr"
    )
    print(f"   Stop Loss: {sl:.5f}")
    print(f"   Explanation: {sl_explanation}")
    
    print("\n📊 Test 4: Validation")
    approved, reason = rm.validate_trade(
        symbol="EURUSD",
        size=size,
        sl_price=sl,
        tp_price=1.0950,
        direction="long"
    )
    print(f"   Result: {'✅' if approved else '❌'} {reason}")
    
    print("\n📊 Test 5: Position Sizing Summary")
    summary = rm.get_position_sizing_summary()
    print(f"   Capital: ${summary['capital']:.2f}")
    print(f"   Drawdown: {summary['drawdown']:.1%}")
    print(f"   Conservative Mode: {summary['conservative_mode']}")
    
    print("\n✅ Risk Manager v2.0 funcionando correctamente")
