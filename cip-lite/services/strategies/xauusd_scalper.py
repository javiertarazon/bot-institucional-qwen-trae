"""
Estrategia Específica para XAUUSD - Scalping M1 Institucional
Basada en: Smart Money Concepts (SMC), Liquidity Sweeps, FVG
Perfil: BALANCED (1% riesgo en $500 = $5/trade, 0.20% = $1/trade)
Arquitectura: Aura-X (Linux Zorin optimizado)
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class XAUUSDConfig:
    """Configuración específica para XAUUSD (Perfil Balanceado)"""
    # Timeframe
    timeframe: str = "M1"

    # Gestión de Riesgo
    risk_per_trade_percent: float = 0.20  # 0.20% del equity
    max_open_trades: int = 1  # XAUUSD permite máximo 1 operación
    sl_distance_points: float = 100.0  # $1.00 de movimiento = 100 points en MT5
    tp_distance_points: float = 150.0  # $1.50 de movimiento = 150 points
    breakeven_trigger_points: float = 60.0  # Mover a BE en +$0.60
    trailing_step_points: float = 30.0  # Arrastre cada $0.30

    # Filtros de Entrada (AJUSTADOS para mayor operatividad)
    max_spread_points: float = 50.0  # Spread máximo aceptable
    min_candle_body_percent: float = 30.0  # Cuerpo mínimo de vela (reducido para más señales)
    blacklist_hours_utc: List[int] = None  # Horarios prohibidos

    # Régimen de Mercado (umbrales más flexibles)
    atr_lateral_max: float = 1.5  # ATR bajo = lateral
    atr_volatile_min: float = 5.0  # ATR alto = volátil
    rsi_overbought: float = 75.0  # Más permisivo
    rsi_oversold: float = 25.0
    rsi_indecision_low: float = 38.0  # Zona de indecisión más estrecha
    rsi_indecision_high: float = 62.0

    # Momentum - más sensible
    momentum_body_threshold: float = 50.0  # Reducido de 60
    momentum_trend_threshold: float = 0.03  # Reducido de 0.05

    def __post_init__(self):
        if self.blacklist_hours_utc is None:
            self.blacklist_hours_utc = [22, 23]  # Baja liquidez NY tarde


class XAUUSDScalper:
    """
    Estrategia de scalping M1 para XAUUSD con tres modos:
    - MOMENTUM: Breakout + velas de gran cuerpo
    - REVERSION: Mean reversion en extremos
    - SMART_MONEY: Liquidity Sweep + FVG (institucional)
    """

    def __init__(self, config: XAUUSDConfig = None):
        self.config = config or XAUUSDConfig()
        self.last_signals: List[Dict] = []
        self.current_position: Optional[Dict] = None

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calcula todos los indicadores necesarios"""
        df = df.copy()

        # EMAs para detectar tendencia
        df['ema_9'] = df['close'].ewm(span=9, adjust=False).mean()
        df['ema_21'] = df['close'].ewm(span=21, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=50, adjust=False).mean()

        # RSI (14 periodos)
        df['rsi'] = self._calculate_rsi(df['close'], 14)

        # ATR (14 periodos)
        df['atr'] = self._calculate_atr(df, 14)

        # Cuerpo de vela como porcentaje del rango
        df['body_pct'] = np.where(
            (df['high'] - df['low']) > 0,
            abs(df['close'] - df['open']) / (df['high'] - df['low']) * 100,
            0
        )

        # Sombra superior e inferior
        df['upper_wick'] = df['high'] - np.maximum(df['close'], df['open'])
        df['lower_wick'] = np.minimum(df['close'], df['open']) - df['low']

        # Fuerza de tendencia
        df['trend_strength'] = (df['ema_9'] - df['ema_21']) / df['ema_21'] * 100

        # Distancia a la EMA 21
        df['distance_to_ema21'] = (df['close'] - df['ema_21']) / df['close'] * 100

        # Detección de FVG (Fair Value Gap)
        df['fvg_bullish'] = (df['low'] > df['high'].shift(2)) & (df['close'].shift(1) > df['high'].shift(2))
        df['fvg_bearish'] = (df['high'] < df['low'].shift(2)) & (df['close'].shift(1) < df['low'].shift(2))

        # Detección de Swing High/Low (últimas 15 velas)
        df['swing_high'] = df['high'].rolling(window=15, center=True).max() == df['high']
        df['swing_low'] = df['low'].rolling(window=15, center=True).min() == df['low']

        return df

    def _calculate_rsi(self, series: pd.Series, period: int = 14) -> pd.Series:
        """RSI usando Wilder's smoothing"""
        delta = series.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']

        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        return atr

    def classify_regime(self, df: pd.DataFrame) -> str:
        """
        Clasifica el régimen actual del mercado:
        - LATERAL: ATR bajo, sin tendencia clara
        - VOLATILE: ATR alto, posibles noticias
        - MOMENTUM: Tendencia clara con velas de gran cuerpo
        - REVERSION: RSI en extremos
        """
        if len(df) < 30:
            return "INSUFFICIENT_DATA"

        last = df.iloc[-1]
        atr_current = last['atr']
        atr_mean = df['atr'].tail(50).mean()

        rsi = last['rsi']
        body_pct = last['body_pct']
        trend = last['trend_strength']

        # Detección de momentum (tendencia + vela fuerte)
        if abs(trend) > 0.01 and body_pct > 50 and atr_current > atr_mean * 0.7:
            return "MOMENTUM"

        # Detección de reversion (RSI extremo)
        if rsi >= self.config.rsi_overbought or rsi <= self.config.rsi_oversold:
            return "REVERSION"

        # Detección de volatilidad alta (ATR por encima del umbral)
        if atr_current > self.config.atr_volatile_min:
            return "VOLATILE"

        # Por defecto: lateral (sin tendencia fuerte)
        return "LATERAL"

    def detect_liquidity_sweep(self, df: pd.DataFrame, lookback: int = 15) -> Optional[str]:
        """
        Detecta barrido de liquidez (Liquidity Sweep) institucional.
        Retorna: "BULLISH_SWEEP", "BEARISH_SWEEP", o None
        """
        if len(df) < lookback + 2:
            return None

        recent = df.tail(lookback + 1)
        last_candle = df.iloc[-1]
        prev_candle = df.iloc[-2]

        # Máximo y mínimo del período
        period_high = recent['high'].max()
        period_low = recent['low'].min()

        # Bullish Sweep: Precio barre mínimo y cierra arriba
        if prev_candle['low'] < period_low and last_candle['close'] > prev_candle['open']:
            return "BULLISH_SWEEP"

        # Bearish Sweep: Precio barre máximo y cierra abajo
        if prev_candle['high'] > period_high and last_candle['close'] < prev_candle['open']:
            return "BEARISH_SWEEP"

        return None

    def detect_fvg_entry(self, df: pd.DataFrame, direction: str) -> Optional[float]:
        """
        Detecta zona de FVG para entrada.
        Retorna: precio de entrada óptimo o None
        """
        if len(df) < 3:
            return None

        last_three = df.tail(3)
        c1 = last_three.iloc[0]  # Vela más antigua
        c3 = last_three.iloc[2]  # Vela más reciente

        if direction == "BUY":
            # Bullish FVG: gap entre high de c1 y low de c3
            if c3['low'] > c1['high']:
                fvg_zone_low = c1['high']
                fvg_zone_high = c3['low']
                return (fvg_zone_low + fvg_zone_high) / 2  # Punto medio
        elif direction == "SELL":
            # Bearish FVG: gap entre low de c1 y high de c3
            if c3['high'] < c1['low']:
                fvg_zone_low = c3['high']
                fvg_zone_high = c1['low']
                return (fvg_zone_low + fvg_zone_high) / 2

        return None

    def generate_signal(self, df: pd.DataFrame, current_spread: float = 30.0) -> Dict:
        """
        Genera señal de trading basada en el régimen y contexto.
        Retorna dict con: signal, entry_price, sl_price, tp_price, reason, regime
        """
        if len(df) < 50:
            return {"signal": "HOLD", "reason": "Datos insuficientes"}

        # Calcular indicadores
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        regime = self.classify_regime(df)

        # Filtrar horario
        current_hour = datetime.now(timezone.utc).hour
        if current_hour in self.config.blacklist_hours_utc:
            return {"signal": "HOLD", "reason": f"Horario en blacklist: {current_hour}h UTC", "regime": regime}

        # Filtrar spread
        if current_spread > self.config.max_spread_points:
            return {"signal": "HOLD", "reason": f"Spread alto: {current_spread}", "regime": regime}

        # Señal simplificada y robusta - Priorizar cruces de EMAs
        prev = df.iloc[-2]

        # === SEÑAL DE CRUCE DE EMAs (más confiable) ===
        ema_cross_up = prev['ema_9'] <= prev['ema_21'] and last['ema_9'] > last['ema_21']
        ema_cross_down = prev['ema_9'] >= prev['ema_21'] and last['ema_9'] < last['ema_21']

        # === SEÑAL DE TENDENCIA FUERTE (sin cruce pero con momentum) ===
        trend_up_strong = (last['ema_9'] > last['ema_21'] and
                          last['close'] > last['ema_9'] and
                          last['close'] > last['open'])
        trend_down_strong = (last['ema_9'] < last['ema_21'] and
                            last['close'] < last['ema_9'] and
                            last['close'] < last['open'])

        signal = "HOLD"
        reason = "Sin señal clara"

        # RSI extremos para filtros
        rsi_extreme_buy = last['rsi'] <= self.config.rsi_oversold
        rsi_extreme_sell = last['rsi'] >= self.config.rsi_overbought

        # Generar señal
        if ema_cross_up and last['body_pct'] >= self.config.min_candle_body_percent:
            signal = "BUY"
            reason = "Cruce alcista de EMAs"
        elif ema_cross_down and last['body_pct'] >= self.config.min_candle_body_percent:
            signal = "SELL"
            reason = "Cruce bajista de EMAs"
        elif trend_up_strong and last['body_pct'] >= 50 and not rsi_extreme_buy:
            signal = "BUY"
            reason = "Tendencia alcista fuerte"
        elif trend_down_strong and last['body_pct'] >= 50 and not rsi_extreme_sell:
            signal = "SELL"
            reason = "Tendencia bajista fuerte"
        elif rsi_extreme_buy and last['close'] > last['open']:
            signal = "BUY"
            reason = f"RSI extremo ({last['rsi']:.0f}) + vela alcista"
        elif rsi_extreme_sell and last['close'] < last['open']:
            signal = "SELL"
            reason = f"RSI extremo ({last['rsi']:.0f}) + vela bajista"

        if signal == "HOLD":
            return {"signal": "HOLD", "reason": reason, "regime": regime}

        # Calcular SL/TP
        entry_price = last['close']
        sl_distance = self.config.sl_distance_points
        tp_distance = self.config.tp_distance_points

        if signal == "BUY":
            sl_price = entry_price - sl_distance * 0.01
            tp_price = entry_price + tp_distance * 0.01
        else:
            sl_price = entry_price + sl_distance * 0.01
            tp_price = entry_price - tp_distance * 0.01

        return {
            "signal": signal,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_distance": sl_distance,
            "tp_distance": tp_distance,
            "reason": reason,
            "regime": regime,
            "rsi": last['rsi'],
            "atr": last['atr'],
            "body_pct": last['body_pct']
        }

    def _momentum_signal(self, df: pd.DataFrame, last: pd.Series) -> Dict:
        """Señal para régimen de Momentum (Breakout)"""
        signal = "HOLD"
        reason = "Sin momentum claro"

        # Bullish: EMA9 > EMA21 > EMA50, cuerpo fuerte
        if (last['ema_9'] > last['ema_21'] and
            last['body_pct'] > self.config.momentum_body_threshold and
            last['close'] > last['open']):
            signal = "BUY"
            reason = "Momentum alcista confirmado"

        # Bearish: EMA9 < EMA21 < EMA50, cuerpo fuerte
        elif (last['ema_9'] < last['ema_21'] and
              last['body_pct'] > self.config.momentum_body_threshold and
              last['close'] < last['open']):
            signal = "SELL"
            reason = "Momentum bajista confirmado"

        # Señal alternativa: cruce de EMAs sin importar cuerpo
        elif last['ema_9'] > last['ema_21'] and df.iloc[-2]['ema_9'] <= df.iloc[-2]['ema_21']:
            signal = "BUY"
            reason = "Cruce alcista de EMAs"
        elif last['ema_9'] < last['ema_21'] and df.iloc[-2]['ema_9'] >= df.iloc[-2]['ema_21']:
            signal = "SELL"
            reason = "Cruce bajista de EMAs"

        if signal == "HOLD":
            return {"signal": "HOLD", "reason": reason, "regime": "MOMENTUM"}

        # Calcular SL/TP en points (asumiendo XAUUSD: 1 point = $0.01)
        entry_price = last['close']
        if signal == "BUY":
            sl_price = entry_price - self.config.sl_distance_points * 0.01
            tp_price = entry_price + self.config.tp_distance_points * 0.01
        else:
            sl_price = entry_price + self.config.sl_distance_points * 0.01
            tp_price = entry_price - self.config.tp_distance_points * 0.01

        return {
            "signal": signal,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_distance": self.config.sl_distance_points,
            "tp_distance": self.config.tp_distance_points,
            "reason": reason,
            "regime": "MOMENTUM",
            "rsi": last['rsi'],
            "atr": last['atr'],
            "body_pct": last['body_pct']
        }

    def _reversion_signal(self, df: pd.DataFrame, last: pd.Series) -> Dict:
        """Señal para régimen de Reversión (RSI extremo) o LATERAL con extremos"""
        signal = "HOLD"
        reason = "Sin divergencia"

        rsi = last['rsi']

        # Sobreventa: buscar BUY
        if rsi <= self.config.rsi_oversold:
            # Confirmar con vela alcista
            if last['close'] > last['open'] and last['lower_wick'] > last['body_pct'] * 0.5:
                signal = "BUY"
                reason = f"Reversión desde sobreventa (RSI={rsi:.1f})"
            elif rsi <= 20:  # Sobreventa extrema - entrada más agresiva
                signal = "BUY"
                reason = f"Sobreventa extrema (RSI={rsi:.1f})"

        # Sobrecompra: buscar SELL
        elif rsi >= self.config.rsi_overbought:
            if last['close'] < last['open'] and last['upper_wick'] > last['body_pct'] * 0.5:
                signal = "SELL"
                reason = f"Reversión desde sobrecompra (RSI={rsi:.1f})"
            elif rsi >= 80:  # Sobrecompra extrema
                signal = "SELL"
                reason = f"Sobrecompra extrema (RSI={rsi:.1f})"

        if signal == "HOLD":
            return {"signal": "HOLD", "reason": reason, "regime": "REVERSION"}

        # SL más ajustado en reversion (mean reversion rápido)
        entry_price = last['close']
        sl_distance = self.config.sl_distance_points * 0.8  # 80% del SL normal
        tp_distance = self.config.tp_distance_points * 0.7  # TP más conservador

        if signal == "BUY":
            sl_price = entry_price - sl_distance * 0.01
            tp_price = entry_price + tp_distance * 0.01
        else:
            sl_price = entry_price + sl_distance * 0.01
            tp_price = entry_price - tp_distance * 0.01

        return {
            "signal": signal,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "tp_price": tp_price,
            "sl_distance": sl_distance,
            "tp_distance": tp_distance,
            "reason": reason,
            "regime": "REVERSION",
            "rsi": rsi
        }

    def _volatile_signal(self, df: pd.DataFrame, last: pd.Series) -> Dict:
        """Señal para régimen Volátil (Smart Money: Liquidity Sweep + FVG)"""
        sweep = self.detect_liquidity_sweep(df)

        if sweep == "BULLISH_SWEEP":
            # Entrada en FVG alcista
            fvg_entry = self.detect_fvg_entry(df, "BUY")
            if fvg_entry:
                return {
                    "signal": "BUY",
                    "entry_price": fvg_entry,
                    "sl_price": last['low'] - 50,  # SL debajo del sweep
                    "tp_price": fvg_entry + self.config.tp_distance_points * 0.01,
                    "sl_distance": 100,
                    "tp_distance": 200,
                    "reason": "Smart Money: Bullish Sweep + FVG",
                    "regime": "VOLATILE",
                    "rsi": last['rsi']
                }

        elif sweep == "BEARISH_SWEEP":
            fvg_entry = self.detect_fvg_entry(df, "SELL")
            if fvg_entry:
                return {
                    "signal": "SELL",
                    "entry_price": fvg_entry,
                    "sl_price": last['high'] + 50,
                    "tp_price": fvg_entry - self.config.tp_distance_points * 0.01,
                    "sl_distance": 100,
                    "tp_distance": 200,
                    "reason": "Smart Money: Bearish Sweep + FVG",
                    "regime": "VOLATILE",
                    "rsi": last['rsi']
                }

        return {"signal": "HOLD", "reason": "Volatilidad sin patrón claro", "regime": "VOLATILE"}

    def calculate_lot_size(self, equity_usd: float, sl_distance_points: float,
                          pip_value_per_minilot: float = 1.0) -> float:
        """
        Calcula lotaje basado en riesgo fijo.
        Para XAUUSD en cuenta Standard: 0.01 lote = 1 onza, 1 point ($0.01) = $0.01.
        pip_value_per_minilot para XAUUSD = $0.10 por punto (0.01 de movimiento).
        """
        risk_usd = equity_usd * (self.config.risk_per_trade_percent / 100.0)

        # Formula: Lot = Riesgo_USD / (SL_distance * valor_por_pip_por_lote_minimo)
        # Para XAUUSD: 1 lote = 100 onzas. SL de 100 points ($1) = $100 por lote.
        raw_lot = risk_usd / (sl_distance_points * pip_value_per_minilot)

        # Normalizar a 2 decimales
        lot = round(raw_lot * 100) / 100

        # Mínimo 0.01, máximo 1.00 (para $500)
        return max(0.01, min(lot, 1.0))


class XAUUSDBacktest:
    """Motor de backtesting específico para XAUUSD"""

    def __init__(self, config: XAUUSDConfig = None, initial_capital: float = 500.0):
        self.config = config or XAUUSDConfig()
        self.strategy = XAUUSDScalper(self.config)
        self.initial_capital = initial_capital
        self.equity_curve = [initial_capital]
        self.trades = []

    def run(self, df: pd.DataFrame) -> Dict:
        """Ejecuta backtest completo"""
        logger.info(f"Iniciando backtest XAUUSD con {len(df)} velas M1")

        capital = self.initial_capital
        position = None
        max_equity = capital

        for i in range(50, len(df)):
            window = df.iloc[:i+1].copy()
            current = window.iloc[-1]

            # Generar señal
            signal_data = self.strategy.generate_signal(window, current_spread=20)

            # Gestionar posición abierta
            if position is not None:
                # Verificar SL
                if position['direction'] == "BUY":
                    if current['low'] <= position['sl_price']:
                        pnl = (position['sl_price'] - position['entry_price']) * position['lot_size'] * 100
                        capital += pnl
                        self.trades.append({**position, 'exit_price': position['sl_price'],
                                           'pnl': pnl, 'exit_reason': 'SL_HIT'})
                        position = None
                    # Verificar TP
                    elif current['high'] >= position['tp_price']:
                        pnl = (position['tp_price'] - position['entry_price']) * position['lot_size'] * 100
                        capital += pnl
                        self.trades.append({**position, 'exit_price': position['tp_price'],
                                           'pnl': pnl, 'exit_reason': 'TP_HIT'})
                        position = None
                    # Trailing Stop
                    elif current['close'] - position['entry_price'] >= self.config.breakeven_trigger_points * 0.01:
                        new_sl = position['entry_price']  # Mover a breakeven
                        if new_sl > position['sl_price']:
                            position['sl_price'] = new_sl

                elif position['direction'] == "SELL":
                    if current['high'] >= position['sl_price']:
                        pnl = (position['entry_price'] - position['sl_price']) * position['lot_size'] * 100
                        capital += pnl
                        self.trades.append({**position, 'exit_price': position['sl_price'],
                                           'pnl': pnl, 'exit_reason': 'SL_HIT'})
                        position = None
                    elif current['low'] <= position['tp_price']:
                        pnl = (position['entry_price'] - position['tp_price']) * position['lot_size'] * 100
                        capital += pnl
                        self.trades.append({**position, 'exit_price': position['tp_price'],
                                           'pnl': pnl, 'exit_reason': 'TP_HIT'})
                        position = None

            # Abrir nueva posición si hay señal
            if position is None and signal_data['signal'] in ('BUY', 'SELL'):
                lot = self.strategy.calculate_lot_size(capital, self.config.sl_distance_points)
                position = {
                    'direction': signal_data['signal'],
                    'entry_price': current['close'],
                    'sl_price': signal_data['sl_price'],
                    'tp_price': signal_data['tp_price'],
                    'lot_size': lot,
                    'entry_time': current.get('time', i),
                    'regime': signal_data.get('regime', 'UNKNOWN'),
                    'reason': signal_data.get('reason', '')
                }

            # Actualizar equity
            if position is None:
                self.equity_curve.append(capital)
            else:
                unrealized = 0
                if position['direction'] == 'BUY':
                    unrealized = (current['close'] - position['entry_price']) * position['lot_size'] * 100
                else:
                    unrealized = (position['entry_price'] - current['close']) * position['lot_size'] * 100
                self.equity_curve.append(capital + unrealized)

            max_equity = max(max_equity, self.equity_curve[-1])

        return self._calculate_results(max_equity)

    def _calculate_results(self, max_equity: float) -> Dict:
        """Calcula métricas de rendimiento"""
        equity = pd.Series(self.equity_curve)
        returns = equity.pct_change().dropna()

        wins = [t for t in self.trades if t['pnl'] > 0]
        losses = [t for t in self.trades if t['pnl'] <= 0]

        total_trades = len(self.trades)
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0

        total_pnl = sum(t['pnl'] for t in self.trades)
        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['pnl']) for t in losses]) if losses else 0

        profit_factor = abs(sum(t['pnl'] for t in wins) / sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else float('inf')

        # Drawdown
        peak = equity.cummax()
        drawdown = (equity - peak) / peak
        max_drawdown = drawdown.min() * 100

        # Sharpe (asumiendo 252 días de trading * 1440 minutos / día = 362880 barras/año)
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252 * 1440)
        else:
            sharpe = 0

        return {
            'initial_capital': self.initial_capital,
            'final_capital': self.equity_curve[-1],
            'total_return_usd': self.equity_curve[-1] - self.initial_capital,
            'total_return_pct': (self.equity_curve[-1] / self.initial_capital - 1) * 100,
            'total_trades': total_trades,
            'winning_trades': len(wins),
            'losing_trades': len(losses),
            'win_rate_pct': win_rate,
            'avg_win_usd': avg_win,
            'avg_loss_usd': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'expectancy_usd': total_pnl / total_trades if total_trades > 0 else 0
        }
