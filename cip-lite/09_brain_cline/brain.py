"""
Módulo Cerebro Cline - v3.0
Análisis y toma de decisiones con lógica de trading avanzada
- Integración ONNX para clasificación de régimen de mercado
- Multi-timeframe analysis
- Signal Memory integration for adaptive learning
- Dynamic indicator weights based on market regime
- Divergence detection
- Volume profile analysis
- Advanced confidence scoring with entropy measurement
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import math
import structlog
import numpy as np
import pandas as pd

logger = structlog.get_logger()

# Importar clasificador ONNX
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python_brain"))
try:
    from onnx_classifier import ONNXRegimeClassifier
    ONNX_AVAILABLE = True
except ImportError:
    ONNX_AVAILABLE = False
    logger.warning("ONNX no disponible, usando clasificación por reglas")

# ==================== ENUMS Y CONSTANTES ====================

class TradingSignal(Enum):
    """Señales de trading posibles"""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class MarketRegime(Enum):
    """Regímenes de mercado detectables"""
    MOMENTUM = "MOMENTUM"
    LATERAL = "LATERAL"
    VOLATILE = "VOLATILE"
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    HIGH_IMPULSE = "HIGH_IMPULSE"  # Velas de gran impulso
    LOW_LIQUIDITY = "LOW_LIQUIDITY"  # Baja liquidez


class DivergenceType(Enum):
    """Tipos de divergencia detectables"""
    BULLISH = "BULLISH"      # Precio baja, RSI sube
    BEARISH = "BEARISH"      # Precio sube, RSI baja
    HIDDEN_BULLISH = "HIDDEN_BULLISH"  # Precio sube, RSI sube más
    HIDDEN_BEARISH = "HIDDEN_BEARISH"  # Precio baja, RSI baja más
    NONE = "NONE"


# ==================== DATACLASSES ====================

@dataclass
class TechnicalSnapshot:
    """Resumen técnico completo del mercado"""
    symbol: str
    timestamp: datetime
    current_price: float
    trend: str  # BULLISH, BEARISH, NEUTRAL
    strength: float  # 0.0 a 1.0
    volatility: str  # HIGH, MEDIUM, LOW
    volatility_value: float  # Valor numérico de volatilidad
    rsi: float
    macd: float
    macd_signal: float
    bb_position: float  # -1 a 1 (posición en Bollinger)
    adx: float
    volume_ratio: float  # Volumen actual vs promedio
    market_regime: str  # MOMENTUM, LATERAL, etc.
    candle_pattern: str  # Pattern detectado en la última vela
    volume_profile: str  # HIGH, NORMAL, LOW, ACCUMULATION, DISTRIBUTION
    support: float
    resistance: float
    divergence: str  # BULLISH, BEARISH, NONE
    key_levels: Dict[str, float]


@dataclass
class MarketAnalysis:
    """Resultado del análisis de mercado"""
    symbol: str
    timestamp: datetime
    trend: str  # BULLISH, BEARISH, NEUTRAL
    volatility: str  # HIGH, MEDIUM, LOW
    strength: float  # 0.0 a 1.0
    confidence: float  # 0.0 a 1.0
    reasoning: List[str]
    technical_score: float
    key_levels: Dict[str, float]
    regime: str = "UNKNOWN"
    divergence: str = "NONE"
    volume_profile: str = "NORMAL"
    summary: str = ""


@dataclass
class TradingDecision:
    """Decisión final de trading"""
    signal: TradingSignal
    confidence: float
    reasoning: str
    suggested_position_size: float
    stop_loss: float
    take_profit: float
    risk_reward_ratio: float
    time_horizon: str  # SCALP, INTRADAY, SWING, POSITION
    urgency: str  # LOW, MEDIUM, HIGH
    entry_price: float = 0.0
    regime: str = "UNKNOWN"
    divergence: str = "NONE"
    market_regime_alignment: float = 0.0  # Qué tan alineada está la señal con el régimen


# ==================== CLASIFICADOR DE RÉGIMEN MEJORADO ====================

class RegimeClassifier:
    """
    Clasificador de régimen de mercado con múltiples métodos:
    - ONNX si está disponible
    - Reglas técnicas como fallback
    - Análisis de volatilidad y volumen
    """
    
    def __init__(self, onnx_classifier=None):
        self.onnx = onnx_classifier
        self.regime_history: List[Tuple[datetime, str]] = []
        self.confidence_history: List[float] = []
    
    def classify(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Clasifica el régimen actual del mercado.
        Returns: (regime, confidence)
        """
        if df is None or len(df) < 21:
            return "LATERAL", 0.5
        
        regime_scores = {}
        
        # 1. Método ONNX (si disponible)
        if self.onnx and len(df) >= 21:
            try:
                onnx_regime, onnx_confidence = self.onnx.predict_with_confidence(df)
                regime_scores[onnx_regime] = regime_scores.get(onnx_regime, 0) + onnx_confidence * 0.5
            except Exception as e:
                logger.warning(f"Error ONNX: {e}")
        
        # 2. Análisis de volatilidad
        try:
            high_low_ratio = (df['high'] / df['low'] - 1).mean()
            if high_low_ratio > 0.015:  # > 1.5% rango promedio
                regime_scores['VOLATILE'] = regime_scores.get('VOLATILE', 0) + 0.3
            elif high_low_ratio < 0.004:  # < 0.4% rango promedio
                regime_scores['LOW_LIQUIDITY'] = regime_scores.get('LOW_LIQUIDITY', 0) + 0.25
        except Exception:
            pass
        
        # 3. Análisis de tendencia (EMA)
        try:
            close = df['close'].values
            ema9 = pd.Series(close).ewm(span=9).mean().values
            ema21 = pd.Series(close).ewm(span=21).mean().values
            ema50 = pd.Series(close).ewm(span=50).mean().values if len(close) >= 50 else None
            
            # Trending up: EMAs alineadas alcistas
            if len(close) >= 3:
                if ema9[-1] > ema21[-1] and ema9[-1] > ema9[-2] > ema9[-3]:
                    regime_scores['TRENDING_UP'] = regime_scores.get('TRENDING_UP', 0) + 0.35
                    # Si además ONNX dijo MOMENTUM, reforzar
                    if 'MOMENTUM' in regime_scores:
                        regime_scores['TRENDING_UP'] += 0.15
                elif ema9[-1] < ema21[-1] and ema9[-1] < ema9[-2] < ema9[-3]:
                    regime_scores['TRENDING_DOWN'] = regime_scores.get('TRENDING_DOWN', 0) + 0.35
                    if 'MOMENTUM' in regime_scores:
                        regime_scores['TRENDING_DOWN'] += 0.15
                else:
                    # EMAs entrecruzadas = lateral
                    regime_scores['LATERAL'] = regime_scores.get('LATERAL', 0) + 0.25
        except Exception:
            pass
        
        # 4. Análisis de impulso (velas)
        try:
            body_sizes = abs(df['close'] - df['open']) / (df['high'] - df['low'] + 1e-10)
            avg_body = body_sizes.mean()
            if avg_body > 0.7:  # Velas con cuerpo grande
                regime_scores['HIGH_IMPULSE'] = regime_scores.get('HIGH_IMPULSE', 0) + 0.25
        except Exception:
            pass
        
        # 5. Determinar régimen ganador
        if not regime_scores:
            return "LATERAL", 0.5
        
        best_regime = max(regime_scores.items(), key=lambda x: x[1])
        confidence = min(1.0, best_regime[1] * 1.5)  # Escalar confianza
        
        # Mapear MOMENTUM a TRENDING_UP/DOWN si aplica
        regime = best_regime[0]
        if regime == "MOMENTUM":
            try:
                ema9_val = pd.Series(df['close'].values).ewm(span=9).mean().iloc[-1]
                ema21_val = pd.Series(df['close'].values).ewm(span=21).mean().iloc[-1]
                regime = "TRENDING_UP" if ema9_val > ema21_val else "TRENDING_DOWN"
            except Exception:
                regime = "TRENDING_UP" if df['close'].iloc[-1] > df['close'].iloc[-20:-1].mean() else "TRENDING_DOWN"
        
        # Guardar historial
        self.regime_history.append((datetime.now(), regime))
        self.confidence_history.append(confidence)
        
        # Mantener historial limitado
        if len(self.regime_history) > 50:
            self.regime_history.pop(0)
            self.confidence_history.pop(0)
        
        return regime, confidence
    
    def get_regime_stability(self, window: int = 10) -> float:
        """
        Calcula la estabilidad del régimen en las últimas N clasificaciones.
        Retorna 0.0 (inestable/cambiante) a 1.0 (muy estable).
        """
        if len(self.regime_history) < 2:
            return 0.5
        
        recent = self.regime_history[-window:]
        regimes = [r for _, r in recent]
        if not regimes:
            return 0.5
        
        most_common = max(set(regimes), key=regimes.count)
        stability = regimes.count(most_common) / len(regimes)
        return stability


# ==================== MOTOR DE ANÁLISIS TÉCNICO ====================

class TechnicalAnalysisEngine:
    """
    Motor de análisis técnico avanzado.
    Calcula indicadores, detecta patrones y divergencias.
    """
    
    @staticmethod
    def get_technical_snapshot(df: pd.DataFrame, symbol: str) -> TechnicalSnapshot:
        """
        Genera un snapshot técnico completo del mercado.
        """
        try:
            close = df['close']
            high = df['high']
            low = df['low']
            volume = df.get('volume', pd.Series([0] * len(df)))
            price = close.iloc[-1]
            
            # --- Indicadores principales ---
            rsi = TechnicalAnalysisEngine._calc_rsi(close)
            macd_line, macd_signal_line, _ = TechnicalAnalysisEngine._calc_macd(close)
            
            # Bollinger Bands position
            bb_mid = close.rolling(20).mean()
            bb_std = close.rolling(20).std()
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            
            bb_pos = 0.0
            if bb_upper.iloc[-1] != bb_lower.iloc[-1]:
                bb_pos = 2 * (price - bb_lower.iloc[-1]) / (bb_upper.iloc[-1] - bb_lower.iloc[-1]) - 1
            
            # ADX
            adx = TechnicalAnalysisEngine._calc_adx(df)
            
            # --- Análisis de volumen ---
            vol_ma20 = volume.rolling(20).mean()
            volume_ratio = volume.iloc[-1] / vol_ma20.iloc[-1] if vol_ma20.iloc[-1] > 0 else 1.0
            
            # Volume profile
            volume_profile = TechnicalAnalysisEngine._analyze_volume_profile(close, volume)
            
            # --- Volatilidad ---
            volatility_val = close.pct_change().rolling(20).std().iloc[-1] * 100
            
            if volatility_val > 3.0:
                volatility = "HIGH"
            elif volatility_val < 0.8:
                volatility = "LOW"
            else:
                volatility = "MEDIUM"
            
            # --- Soportes y resistencias dinámicos ---
            support, resistance = TechnicalAnalysisEngine._find_dynamic_sr(high, low, close)
            
            # --- Divergencias ---
            divergence = TechnicalAnalysisEngine._detect_divergence(close, rsi)
            
            # --- Patrón de vela ---
            candle_pattern = TechnicalAnalysisEngine._detect_candle_pattern(df)
            
            # --- Tendencia ---
            trend, strength = TechnicalAnalysisEngine._determine_trend(close)
            
            # --- Régimen ---
            market_regime = TechnicalAnalysisEngine._quick_regime_classify(df)
            
            return TechnicalSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=price,
                trend=trend,
                strength=strength,
                volatility=volatility,
                volatility_value=volatility_val,
                rsi=rsi,
                macd=macd_line.iloc[-1] if hasattr(macd_line, 'iloc') else 0,
                macd_signal=macd_signal_line.iloc[-1] if hasattr(macd_signal_line, 'iloc') else 0,
                bb_position=bb_pos,
                adx=adx,
                volume_ratio=volume_ratio,
                market_regime=market_regime,
                candle_pattern=candle_pattern,
                volume_profile=volume_profile,
                support=support,
                resistance=resistance,
                divergence=divergence,
                key_levels={
                    'support': support,
                    'resistance': resistance,
                    'bb_upper': bb_upper.iloc[-1] if hasattr(bb_upper, 'iloc') else price * 1.02,
                    'bb_lower': bb_lower.iloc[-1] if hasattr(bb_lower, 'iloc') else price * 0.98,
                    'ema9': pd.Series(close).ewm(span=9).mean().iloc[-1],
                    'ema21': pd.Series(close).ewm(span=21).mean().iloc[-1],
                }
            )
        except Exception as e:
            logger.error(f"Error generando snapshot técnico: {e}", exc_info=True)
            price = df['close'].iloc[-1] if len(df) > 0 else 0
            return TechnicalSnapshot(
                symbol=symbol,
                timestamp=datetime.now(),
                current_price=price,
                trend="NEUTRAL",
                strength=0.5,
                volatility="MEDIUM",
                volatility_value=1.0,
                rsi=50,
                macd=0,
                macd_signal=0,
                bb_position=0,
                adx=20,
                volume_ratio=1.0,
                market_regime="UNKNOWN",
                candle_pattern="UNKNOWN",
                volume_profile="NORMAL",
                support=price * 0.98,
                resistance=price * 1.02,
                divergence="NONE",
                key_levels={'support': price * 0.98, 'resistance': price * 1.02}
            )
    
    @staticmethod
    def _calc_rsi(data: pd.Series, period: int = 14) -> float:
        """Calcula RSI"""
        if len(data) < period + 1:
            return 50
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else 50
    
    @staticmethod
    def _calc_macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """Calcula MACD"""
        if len(data) < slow:
            return pd.Series([0]), pd.Series([0]), pd.Series([0])
        ema_fast = data.ewm(span=fast).mean()
        ema_slow = data.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    @staticmethod
    def _calc_adx(df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ADX (Average Directional Index)"""
        if len(df) < period + 1:
            return 20
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs()
        ], axis=1).max(axis=1)
        
        # Directional Movement
        up_move = high - high.shift()
        down_move = low.shift() - low
        
        plus_dm = pd.Series(0.0, index=high.index)
        minus_dm = pd.Series(0.0, index=high.index)
        
        mask_up = (up_move > down_move) & (up_move > 0)
        mask_down = (down_move > up_move) & (down_move > 0)
        
        plus_dm[mask_up] = up_move[mask_up]
        minus_dm[mask_down] = down_move[mask_down]
        
        # Smooth
        atr = tr.rolling(period).mean().replace(0, 1e-10)
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        # ADX
        dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10)
        adx = dx.rolling(period).mean()
        
        return adx.iloc[-1] if not adx.empty else 20
    
    @staticmethod
    def _analyze_volume_profile(close: pd.Series, volume: pd.Series) -> str:
        """Analiza perfil de volumen"""
        if len(close) < 20 or volume.sum() == 0:
            return "NORMAL"
        
        vol_ma20 = volume.rolling(20).mean()
        current_vol_ratio = volume.iloc[-1] / vol_ma20.iloc[-1] if vol_ma20.iloc[-1] > 0 else 1.0
        
        # Price change
        price_change = (close.iloc[-1] / close.iloc[-10] - 1) * 100 if len(close) >= 10 else 0
        
        # Acumulación: precio subiendo con volumen creciente
        if current_vol_ratio > 1.3 and price_change > 0.5:
            return "ACCUMULATION"
        # Distribución: precio bajando con volumen creciente
        elif current_vol_ratio > 1.3 and price_change < -0.5:
            return "DISTRIBUTION"
        # Alta actividad
        elif current_vol_ratio > 1.3:
            return "HIGH"
        # Baja actividad
        elif current_vol_ratio < 0.6:
            return "LOW"
        else:
            return "NORMAL"
    
    @staticmethod
    def _find_dynamic_sr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> Tuple[float, float]:
        """
        Encuentra soporte y resistencia dinámicos basados en
        los puntos de inflexión locales (swing highs/lows).
        """
        if len(close) < window:
            price = close.iloc[-1] if not close.empty else 0
            return price * 0.98, price * 1.02
        
        # Buscar swing highs y lows
        swings_high = []
        swings_low = []
        
        for i in range(window, len(high) - window):
            if high.iloc[i] == high.iloc[i-window:i+window+1].max():
                swings_high.append(high.iloc[i])
            if low.iloc[i] == low.iloc[i-window:i+window+1].min():
                swings_low.append(low.iloc[i])
        
        if not swings_high:
            resistance = high.rolling(20).max().iloc[-1]
        else:
            # Usar el swing high más reciente como resistencia
            resistance = np.median(swings_high[-3:]) if len(swings_high) >= 3 else swings_high[-1]
        
        if not swings_low:
            support = low.rolling(20).min().iloc[-1]
        else:
            support = np.median(swings_low[-3:]) if len(swings_low) >= 3 else swings_low[-1]
        
        # Asegurar que support < resistance
        if support >= resistance:
            price = close.iloc[-1]
            support = price * 0.98
            resistance = price * 1.02
        
        return support, resistance
    
    @staticmethod
    def _detect_divergence(close: pd.Series, rsi_values: pd.Series = None) -> str:
        """
        Detecta divergencias entre precio y RSI.
        Bullish: precio hace mínimo más bajo, RSI hace mínimo más alto
        Bearish: precio hace máximo más alto, RSI hace máximo más bajo
        """
        if len(close) < 30:
            return "NONE"
        
        if rsi_values is None or isinstance(rsi_values, (int, float)):
            # Calcular RSI como serie
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 1e-10)
            rsi_values = 100 - (100 / (1 + rs))
        
        if not isinstance(rsi_values, pd.Series) or len(rsi_values) < 30:
            return "NONE"
        
        try:
            # Encontrar 2 peaks/troughs recientes
            price_window = close.iloc[-30:]
            rsi_window = rsi_values.iloc[-30:]
            
            # Últimos 2 mínimos
            min_idx_1 = price_window.idxmin()
            rsi_at_min_1 = rsi_window.loc[min_idx_1]
            
            # Excluir el mínimo encontrado y buscar el segundo
            temp_prices = price_window.drop(min_idx_1)
            if temp_prices.empty:
                return "NONE"
            min_idx_2 = temp_prices.idxmin()
            rsi_at_min_2 = rsi_window.loc[min_idx_2]
            
            # Verificar bull divergence: precio baja, RSI sube
            if (price_window.loc[min_idx_2] > price_window.loc[min_idx_1] and
                rsi_at_min_2 < rsi_at_min_1):
                return "BULLISH"
            
            # Últimos 2 máximos
            max_idx_1 = price_window.idxmax()
            rsi_at_max_1 = rsi_window.loc[max_idx_1]
            
            temp_prices = price_window.drop(max_idx_1)
            if temp_prices.empty:
                return "NONE"
            max_idx_2 = temp_prices.idxmax()
            rsi_at_max_2 = rsi_window.loc[max_idx_2]
            
            # Verificar bear divergence: precio sube, RSI baja
            if (price_window.loc[max_idx_2] < price_window.loc[max_idx_1] and
                rsi_at_max_2 > rsi_at_max_1):
                return "BEARISH"
            
        except Exception:
            pass
        
        return "NONE"
    
    @staticmethod
    def _detect_candle_pattern(df: pd.DataFrame) -> str:
        """
        Detecta patrones de velas en los últimos 3 candles.
        """
        if len(df) < 3:
            return "UNKNOWN"
        
        open_p = df['open'].values
        high_p = df['high'].values
        low_p = df['low'].values
        close_p = df['close'].values
        
        # Últimas 3 velas
        c1_open, c1_high, c1_low, c1_close = open_p[-1], high_p[-1], low_p[-1], close_p[-1]
        c2_open, c2_high, c2_low, c2_close = open_p[-2], high_p[-2], low_p[-2], close_p[-2]
        c3_open, c3_high, c3_low, c3_close = open_p[-3], high_p[-3], low_p[-3], close_p[-3]
        
        c1_body = abs(c1_close - c1_open)
        c1_range = c1_high - c1_low
        c1_upper_wick = c1_high - max(c1_open, c1_close)
        c1_lower_wick = min(c1_open, c1_close) - c1_low
        
        # Doji: cuerpo muy pequeño
        if c1_range > 0 and c1_body / c1_range < 0.1:
            return "DOJI"
        
        # Martillo: mecha inferior larga, cuerpo pequeño superior
        if (c1_lower_wick > 2 * c1_body and c1_upper_wick < c1_body and 
            c1_range > 0 and c1_body / c1_range < 0.3):
            return "HAMMER"
        
        # Estrella fugaz: mecha superior larga, cuerpo pequeño inferior
        if (c1_upper_wick > 2 * c1_body and c1_lower_wick < c1_body and
            c1_range > 0 and c1_body / c1_range < 0.3):
            return "SHOOTING_STAR"
        
        # Engulfing alcista
        if (c1_close > c1_open and c2_close < c2_open and
            c1_open < c2_close and c1_close > c2_open):
            return "BULLISH_ENGULFING"
        
        # Engulfing bajista
        if (c1_close < c1_open and c2_close > c2_open and
            c1_open > c2_close and c1_close < c2_open):
            return "BEARISH_ENGULFING"
        
        # Three white soldiers (3 velas verdes consecutivas)
        if (c1_close > c1_open and c2_close > c2_open and c3_close > c3_open and
            c1_close > c2_close > c3_close):
            return "THREE_WHITE_SOLDIERS"
        
        # Three black crows (3 velas rojas consecutivas)
        if (c1_close < c1_open and c2_close < c2_open and c3_close < c3_open and
            c1_close < c2_close < c3_close):
            return "THREE_BLACK_CROWS"
        
        return "NONE"
    
    @staticmethod
    def _determine_trend(close: pd.Series) -> Tuple[str, float]:
        """
        Determina la tendencia usando EMAs.
        Returns: (trend, strength)
        """
        if len(close) < 21:
            return "NEUTRAL", 0.5
        
        ema9 = close.ewm(span=9).mean()
        ema21 = close.ewm(span=21).mean()
        ema50 = close.ewm(span=50).mean() if len(close) >= 50 else None
        
        price = close.iloc[-1]
        
        # Scoring
        bullish_score = 0
        bearish_score = 0
        
        # Price vs EMAs
        if price > ema9.iloc[-1]:
            bullish_score += 1
        else:
            bearish_score += 1
        
        if price > ema21.iloc[-1]:
            bullish_score += 1
        else:
            bearish_score += 1
        
        if ema50 is not None:
            if price > ema50.iloc[-1]:
                bullish_score += 1
            else:
                bearish_score += 1
        
        # EMA alignment
        if ema9.iloc[-1] > ema21.iloc[-1]:
            bullish_score += 1
        else:
            bearish_score += 1
        
        if ema50 is not None and ema21.iloc[-1] > ema50.iloc[-1]:
            bullish_score += 1
        elif ema50 is not None:
            bearish_score += 1
        
        # Momentum reciente
        price_change_5 = (close.iloc[-1] / close.iloc[-5] - 1) * 100 if len(close) >= 5 else 0
        if price_change_5 > 0.5:
            bullish_score += 1
        elif price_change_5 < -0.5:
            bearish_score += 1
        
        total = bullish_score + bearish_score
        if total == 0:
            return "NEUTRAL", 0.5
        
        if bullish_score > bearish_score:
            strength = bullish_score / total
            return "BULLISH", strength
        elif bearish_score > bullish_score:
            strength = bearish_score / total
            return "BEARISH", strength
        else:
            return "NEUTRAL", 0.5
    
    @staticmethod
    def _quick_regime_classify(df: pd.DataFrame) -> str:
        """Clasificación rápida de régimen sin ONNX"""
        if len(df) < 21:
            return "UNKNOWN"
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        
        # Volatilidad
        atr = pd.Series(high - low).rolling(14).mean().iloc[-1]
        price = close[-1]
        volatility_pct = atr / price * 100
        
        # Tendencia
        ema9 = pd.Series(close).ewm(span=9).mean().values[-1]
        ema21 = pd.Series(close).ewm(span=21).mean().values[-1]
        
        trending = abs(ema9 - ema21) / price * 100
        
        if trending > 0.15 and volatility_pct > 0.5:
            return "MOMENTUM"
        elif volatility_pct < 0.2:
            return "LATERAL"
        elif volatility_pct > 1.0:
            return "VOLATILE"
        elif ema9 > ema21:
            return "TRENDING_UP"
        else:
            return "TRENDING_DOWN"


# ==================== CONSULTOR DE MEMORIA ====================

class MemoryConsultant:
    """
    Consulta la memoria de operaciones (Signal Memory) para
    ajustar decisiones basadas en aprendizaje histórico.
    """
    
    def __init__(self, memory_module=None):
        self.memory = memory_module
        self.insights_cache: Dict[str, Dict] = {}
        self.cache_expiry: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(hours=1)
    
    def get_adaptive_weights(self, symbol: str, regime: str) -> Dict[str, float]:
        """
        Obtiene pesos adaptativos para indicadores basados en
        el rendimiento histórico para este símbolo y régimen.
        """
        if not self.memory:
            # Pesos por defecto
            return self._default_weights(regime)
        
        # Check cache
        cache_key = f"{symbol}_{regime}"
        if cache_key in self.insights_cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                return self.insights_cache[cache_key]
        
        try:
            insights = self.memory.get_insights(symbol)
            if insights.get('status') != 'success':
                return self._default_weights(regime)
            
            # Ajustar pesos basados en correlaciones históricas
            weights = self._default_weights(regime)
            correlations = insights.get('correlations', {})
            
            if correlations:
                for indicator, corr in correlations.items():
                    if indicator in weights:
                        # Ajustar peso según correlación positiva/negativa
                        if corr > 0.2:
                            weights[indicator] = min(1.0, weights[indicator] + 0.1)
                        elif corr < -0.2:
                            weights[indicator] = max(0.1, weights[indicator] - 0.1)
            
            # Cache
            self.insights_cache[cache_key] = weights
            self.cache_expiry[cache_key] = datetime.now() + self.cache_ttl
            
            return weights
            
        except Exception as e:
            logger.warning(f"Error obteniendo pesos adaptativos: {e}")
            return self._default_weights(regime)
    
    def _default_weights(self, regime: str) -> Dict[str, float]:
        """Pesos por defecto según régimen"""
        if regime in ("MOMENTUM", "TRENDING_UP"):
            return {
                'rsi': 0.8,
                'macd': 1.0,
                'adx': 1.0,
                'volume': 0.7,
                'bollinger': 0.5,
                'sma_crossover': 0.9,
            }
        elif regime == "TRENDING_DOWN":
            return {
                'rsi': 1.0,
                'macd': 0.9,
                'adx': 0.8,
                'volume': 0.8,
                'bollinger': 0.6,
                'sma_crossover': 0.7,
            }
        elif regime == "VOLATILE":
            return {
                'rsi': 1.0,
                'macd': 0.5,
                'adx': 0.3,
                'volume': 0.6,
                'bollinger': 1.0,
                'sma_crossover': 0.2,
            }
        else:  # LATERAL
            return {
                'rsi': 1.0,
                'macd': 0.4,
                'adx': 0.2,
                'volume': 0.5,
                'bollinger': 0.8,
                'sma_crossover': 0.3,
            }
    
    def should_override_decision(self, symbol: str, signal: str, 
                                  confidence: float) -> Optional[str]:
        """
        Verifica si la memoria sugiere anular la decisión.
        Retorna razón de anulación o None.
        """
        if not self.memory:
            return None
        
        try:
            insights = self.memory.get_insights(symbol, period_days=3)
            if insights.get('status') != 'success':
                return None
            
            loss_streak = insights.get('loss_streak', 0)
            win_rate = insights.get('win_rate', 0.5)
            
            # 3+ pérdidas consecutivas → no operar aunque señal sea fuerte
            if loss_streak >= 3:
                return f"MEMORY_OVERRIDE: {loss_streak} pérdidas consecutivas - pausa recomendada"
            
            # Si win_rate < 30% en últimas 10 ops, reducir confianza
            if win_rate < 0.3 and confidence > 0.5:
                return f"MEMORY_OVERRIDE: Win rate bajo ({win_rate:.0%}) - reducir confianza"
            
            return None
            
        except Exception:
            return None


# ==================== CEREBRO PRINCIPAL ====================

class BrainClineModule:
    """
    Cerebro del sistema basado en Cline v3.0
    Analiza mercado usando múltiples timeframes y genera decisiones de trading
    Integración: ONNX, Signal Memory, multi-timeframe, divergencias
    """
    
    def __init__(self, memory_module=None):
        self.analysis_history: List[MarketAnalysis] = []
        self.decision_history: List[TradingDecision] = []
        self.snapshot_history: List[TechnicalSnapshot] = []
        self.risk_tolerance = 0.02  # 2% risk per trade
        self.checkpoint_module = None
        
        # Inicializar clasificador ONNX
        self.onnx_classifier = None
        if ONNX_AVAILABLE:
            try:
                self.onnx_classifier = ONNXRegimeClassifier()
                logger.info("🧠 Brain Cline v3.0 con ONNX inicializado")
            except Exception as e:
                logger.warning(f"No se pudo cargar ONNX: {e}")
        else:
            logger.info("🧠 Brain Cline v3.0 inicializado (modo reglas)")
        
        # Componentes internos
        self.regime_classifier = RegimeClassifier(self.onnx_classifier)
        self.tech_engine = TechnicalAnalysisEngine()
        self.memory_consultant = MemoryConsultant(memory_module)
        
        # Estado interno
        self.last_symbols_analyzed: Dict[str, datetime] = {}
        self.alert_history: List[Dict] = []
        
        # Configuración desde variable de entorno o default
        self.config = {
            'min_confidence_threshold': 0.55,
            'min_adx_for_trend': 22,
            'signal_coherence_threshold': 0.5,
            'divergence_weight': 0.3,
            'volume_conviction_weight': 0.2,
            'regime_alignment_weight': 0.15,
            'technical_weight': 0.35,
        }
        
        # Cargar configuración externa si existe
        self._load_external_config()
    
    def _load_external_config(self):
        """Carga configuración desde config.json si existe"""
        try:
            config_path = Path(__file__).parent.parent / "config.json"
            if config_path.exists():
                import json
                with open(config_path) as f:
                    ext_config = json.load(f)
                
                # Extraer brain-related config
                brain_config = ext_config.get('brain', {})
                if brain_config:
                    self.config.update(brain_config)
                    logger.info(f"Configuración Brain cargada: {len(brain_config)} parámetros")
        except Exception as e:
            logger.debug(f"No se pudo cargar config externa: {e}")
    
    def set_checkpoint_module(self, checkpoint_module):
        """Inyecta el módulo de checkpoint para recuperación"""
        self.checkpoint_module = checkpoint_module
    
    def analyze_market(self, df: pd.DataFrame, symbol: str) -> MarketAnalysis:
        """
        Analiza condiciones de mercado y genera análisis completo.
        Soporta multi-timeframe si el DataFrame contiene suficientes datos.
        """
        try:
            price = df['close'].iloc[-1] if isinstance(df, pd.DataFrame) else 0
            
            reasoning = []
            
            # ========== 1. SNAPSHOT TÉCNICO COMPLETO ==========
            snapshot = self.tech_engine.get_technical_snapshot(df, symbol)
            self.snapshot_history.append(snapshot)
            
            reasoning.append(f"Precio: ${price:.2f} | Tendencia: {snapshot.trend}")
            reasoning.append(f"RSI: {snapshot.rsi:.1f} | ADX: {snapshot.adx:.1f}")
            reasoning.append(f"Régimen: {snapshot.market_regime}")
            reasoning.append(f"Volatilidad: {snapshot.volatility} ({snapshot.volatility_value:.2f}%)")
            
            if snapshot.divergence != "NONE":
                reasoning.append(f"⚠️ Divergencia {snapshot.divergence} detectada")
            
            if snapshot.candle_pattern != "NONE" and snapshot.candle_pattern != "UNKNOWN":
                reasoning.append(f"Patrón de vela: {snapshot.candle_pattern}")
            
            reasoning.append(f"Volumen: {snapshot.volume_profile} (ratio: {snapshot.volume_ratio:.2f}x)")
            
            # ========== 2. CLASIFICACIÓN DE RÉGIMEN ==========
            regime, onnx_confidence = self.regime_classifier.classify(df)
            
            reasoning.append(f"Régimen clasificado: {regime} (confianza: {onnx_confidence:.2%})")
            
            # ========== 3. PESOS ADAPTATIVOS DESDE MEMORIA ==========
            adaptive_weights = self.memory_consultant.get_adaptive_weights(symbol, regime)
            
            # ========== 4. ANÁLISIS MULTI-TIMEFRAME ==========
            mrf_analysis = self._analyze_multi_frame(df)
            if mrf_analysis:
                reasoning.append(f"Multi-timeframe: {mrf_analysis['overall_trend']} (score: {mrf_analysis['coherence']:.2f})")
                if mrf_analysis['coherence'] < 0.5:
                    reasoning.append("⚠️ Timeframes en conflicto - precaución")
            
            # ========== 5. CÁLCULO DE SCORE TÉCNICO ==========
            technical_score = self._calculate_technical_score(
                snapshot, regime, mrf_analysis, adaptive_weights
            )
            
            # ========== 6. DETERMINAR TENDENCIA ==========
            trend = snapshot.trend
            
            # ========== 7. CALCULAR CONFIANZA MEJORADA ==========
            confidence = self._calculate_enhanced_confidence(
                snapshot, regime, technical_score, mrf_analysis
            )
            
            # ========== 8. DETECTAR ALERTAS ==========
            alerts = self._detect_alerts(snapshot, symbol)
            if alerts:
                for alert in alerts:
                    reasoning.append(f"🚨 {alert}")
            
            # ========== 9. CONSTRUIR ANÁLISIS ==========
            analysis = MarketAnalysis(
                symbol=symbol,
                timestamp=datetime.now(),
                trend=trend,
                volatility=snapshot.volatility,
                strength=snapshot.strength,
                confidence=min(confidence, 1.0),
                reasoning=reasoning,
                technical_score=technical_score,
                key_levels={
                    'support': snapshot.support,
                    'resistance': snapshot.resistance,
                    'entry_zone': snapshot.support + (snapshot.resistance - snapshot.support) * 0.3,
                    'stop_loss_zone': snapshot.support * 0.995,
                    'take_profit_zone': snapshot.resistance * 1.005,
                },
                regime=regime,
                divergence=snapshot.divergence,
                volume_profile=snapshot.volume_profile,
            )
            
            self.analysis_history.append(analysis)
            
            # Limitar historial
            if len(self.analysis_history) > 200:
                self.analysis_history = self.analysis_history[-200:]
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error en el análisis de mercado: {e}", exc_info=True)
            raise
    
    def _analyze_multi_frame(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Analiza múltiples timeframes si hay suficientes datos.
        Retorna tendencia general y coherencia entre timeframes.
        """
        if df is None or len(df) < 50:
            return None
        
        close = df['close']
        
        # Timeframe 1: Corto (últimas 5 velas)
        tf1_trend = "BULLISH" if close.iloc[-1] > close.iloc[-5] else "BEARISH" if close.iloc[-1] < close.iloc[-5] else "NEUTRAL"
        tf1_strength = abs(close.iloc[-1] / close.iloc[-5] - 1) * 100
        
        # Timeframe 2: Medio (últimas 20 velas)
        tf2_trend = "BULLISH" if close.iloc[-1] > close.iloc[-20] else "BEARISH" if close.iloc[-1] < close.iloc[-20] else "NEUTRAL"
        tf2_strength = abs(close.iloc[-1] / close.iloc[-20] - 1) * 100
        
        # Timeframe 3: Largo (últimas 50 velas)
        if len(close) >= 50:
            tf3_trend = "BULLISH" if close.iloc[-1] > close.iloc[-50] else "BEARISH" if close.iloc[-1] < close.iloc[-50] else "NEUTRAL"
            tf3_strength = abs(close.iloc[-1] / close.iloc[-50] - 1) * 100
        else:
            tf3_trend = tf2_trend
            tf3_strength = tf2_strength
        
        # Coherencia entre timeframes
        trends = [tf1_trend, tf2_trend, tf3_trend]
        coherent = all(t == tf1_trend for t in trends if t != "NEUTRAL")
        
        bull_count = trends.count("BULLISH")
        bear_count = trends.count("BEARISH")
        
        if bull_count > bear_count:
            overall = "BULLISH"
        elif bear_count > bull_count:
            overall = "BEARISH"
        else:
            overall = "NEUTRAL"
        
        # Score de coherencia (qué tan alineados están)
        if bull_count + bear_count > 0:
            coherence = max(bull_count, bear_count) / (bull_count + bear_count)
        else:
            coherence = 0.5  # Todos neutrales
        
        return {
            'tf1': {'trend': tf1_trend, 'strength': tf1_strength},
            'tf2': {'trend': tf2_trend, 'strength': tf2_strength},
            'tf3': {'trend': tf3_trend, 'strength': tf3_strength},
            'overall_trend': overall,
            'coherence': coherence,
            'coherent': coherent,
        }
    
    def _calculate_technical_score(self, snapshot: TechnicalSnapshot,
                                    regime: str,
                                    mrf_analysis: Optional[Dict],
                                    weights: Dict[str, float]) -> float:
        """
        Calcula score técnico ponderado usando múltiples indicadores.
        Retorna 0.0 a 1.0 (más alto = mejor setup).
        """
        score = 0.0
        total_weight = 0.0
        
        # 1. RSI Score (0-1)
        rsi = snapshot.rsi
        if rsi < 30 or rsi > 70:
            # Zonas extremas (sobreventa/sobrecompra)
            if rsi < 30:
                rsi_score = (30 - rsi) / 30  # Más bajo RSI = más sobreventa
            else:
                rsi_score = (rsi - 70) / 30  # Más alto RSI = más sobrecompra
            
            # Ajustar según tendencia: sobreventa en tendencia alcista es mejor
            if snapshot.trend == "BULLISH" and rsi < 30:
                rsi_score *= 1.2
            elif snapshot.trend == "BEARISH" and rsi > 70:
                rsi_score *= 1.2
        else:
            rsi_score = abs(rsi - 50) / 30  # Distancia del centro
        
        weight = weights.get('rsi', 0.8)
        score += min(1.0, rsi_score) * weight
        total_weight += weight
        
        # 2. MACD Score
        macd = snapshot.macd
        macd_signal = snapshot.macd_signal
        
        if abs(macd) > 0:
            macd_strength = abs(macd - macd_signal) / abs(macd)
            macd_score = min(1.0, macd_strength)
            
            # MACD positivo en trend alcista = mejor
            if macd > 0 and snapshot.trend == "BULLISH":
                macd_score *= 1.2
            elif macd < 0 and snapshot.trend == "BEARISH":
                macd_score *= 1.2
        else:
            macd_score = 0.3
        
        weight = weights.get('macd', 0.9)
        score += min(1.0, macd_score) * weight
        total_weight += weight
        
        # 3. ADX Score
        adx = snapshot.adx
        if adx > 25:
            adx_score = min(1.0, (adx - 25) / 50)  # Fuerza de tendencia
        else:
            adx_score = adx / 50  # Tendencia débil
        
        weight = weights.get('adx', 0.7)
        score += min(1.0, adx_score) * weight
        total_weight += weight
        
        # 4. Bollinger Position Score
        bb_pos = snapshot.bb_position
        if abs(bb_pos) > 0.5:
            bb_score = abs(bb_pos)  # Lejos del centro = movimiento
        else:
            bb_score = 0.3
        
        weight = weights.get('bollinger', 0.6)
        score += min(1.0, bb_score) * weight
        total_weight += weight
        
        # 5. Divergencia Score
        if snapshot.divergence == "BULLISH":
            div_score = 0.8
        elif snapshot.divergence == "BEARISH":
            div_score = 0.8
        else:
            div_score = 0.4
        
        score += div_score * self.config.get('divergence_weight', 0.3)
        total_weight += self.config.get('divergence_weight', 0.3)
        
        # 6. Volumen Score
        vol = snapshot.volume_ratio
        if vol > 1.5:
            vol_score = min(1.0, (vol - 1.5) / 2)  # Volumen alto
        elif vol < 0.5:
            vol_score = 0.3  # Volumen bajo
        else:
            vol_score = 0.5
        
        weight = weights.get('volume', 0.5)
        score += vol_score * weight * self.config.get('volume_conviction_weight', 0.2)
        total_weight += weight * self.config.get('volume_conviction_weight', 0.2)
        
        # 7. Multi-timeframe Coherence
        if mrf_analysis:
            coherence_score = mrf_analysis['coherence']
            score += coherence_score * 0.15
            total_weight += 0.15
        
        # 8. Regime alignment
        regime_alignment = self._calculate_regime_alignment(snapshot.trend, snapshot.market_regime)
        score += regime_alignment * self.config.get('regime_alignment_weight', 0.15)
        total_weight += self.config.get('regime_alignment_weight', 0.15)
        
        # Normalizar
        if total_weight > 0:
            final_score = score / total_weight
        else:
            final_score = 0.5
        
        return min(1.0, max(0.0, final_score))
    
    def _calculate_regime_alignment(self, trend: str, regime: str) -> float:
        """
        Calcula qué tan alineada está la tendencia con el régimen.
        """
        alignments = {
            ('BULLISH', 'MOMENTUM'): 1.0,
            ('BULLISH', 'TRENDING_UP'): 1.0,
            ('BULLISH', 'HIGH_IMPULSE'): 0.9,
            ('BULLISH', 'VOLATILE'): 0.6,
            ('BULLISH', 'LATERAL'): 0.3,
            ('BEARISH', 'MOMENTUM'): 1.0,
            ('BEARISH', 'TRENDING_DOWN'): 1.0,
            ('BEARISH', 'HIGH_IMPULSE'): 0.9,
            ('BEARISH', 'VOLATILE'): 0.6,
            ('BEARISH', 'LATERAL'): 0.3,
            ('NEUTRAL', 'LATERAL'): 1.0,
            ('NEUTRAL', 'VOLATILE'): 0.5,
        }
        return alignments.get((trend, regime), 0.5)
    
    def _calculate_enhanced_confidence(self, snapshot: TechnicalSnapshot,
                                        regime: str,
                                        technical_score: float,
                                        mrf_analysis: Optional[Dict]) -> float:
        """
        Calcula confianza mejorada considerando múltiples factores:
        - Score técnico
        - Estabilidad del régimen
        - Coherencia multi-timeframe
        - Volumen conviction
        - Entropía (diversidad de señales)
        """
        confidence = 0.0
        factors_used = 0
        
        # 1. Base: Score técnico
        confidence += technical_score * self.config.get('technical_weight', 0.35)
        factors_used += self.config.get('technical_weight', 0.35)
        
        # 2. Estabilidad del régimen
        regime_stability = self.regime_classifier.get_regime_stability(window=10)
        confidence += regime_stability * 0.15
        factors_used += 0.15
        
        # 3. Coherencia multi-timeframe
        if mrf_analysis:
            coherence = mrf_analysis['coherence']
            confidence += coherence * 0.15
            factors_used += 0.15
        
        # 4. Volumen conviction
        vol_conviction = min(1.0, max(0.0, (snapshot.volume_ratio - 0.5) / 2))
        confidence += vol_conviction * 0.10
        factors_used += 0.10
        
        # 5. Fuerza de tendencia (ADX basado)
        adx_factor = min(1.0, snapshot.adx / 50)
        confidence += adx_factor * 0.10
        factors_used += 0.10
        
        # 6. Penalización por entropía (señales contradictorias)
        entropy_penalty = self._calculate_entropy_penalty(snapshot)
        confidence -= entropy_penalty * 0.10
        factors_used += 0.10
        
        # Bonus por divergencias
        if snapshot.divergence in ("BULLISH", "BEARISH"):
            confidence += 0.10
            factors_used += 0.10
        
        # Penalización por volumen bajo
        if snapshot.volume_profile == "LOW":
            confidence -= 0.08
            factors_used += 0.08
        
        # Normalizar
        if factors_used > 0:
            confidence = confidence / factors_used
        else:
            confidence = 0.5
        
        return min(1.0, max(0.1, confidence))
    
    def _calculate_entropy_penalty(self, snapshot: TechnicalSnapshot) -> float:
        """
        Calcula penalización por señales contradictorias.
        Ej: RSI sobrecompra + MACD positivo = señales mixtas.
        """
        contradictions = 0
        total_pairs = 0
        
        # RSI extremo vs MACD
        if snapshot.rsi > 70:  # Sobrecompra
            if snapshot.macd > 0:
                contradictions += 1
            total_pairs += 1
        elif snapshot.rsi < 30:  # Sobreventa
            if snapshot.macd < 0:
                contradictions += 1
            total_pairs += 1
        
        # ADX bajo vs trend definido
        if snapshot.adx < 22 and snapshot.trend != "NEUTRAL":
            contradictions += 1
            total_pairs += 1
        
        # Bollinger vs tendencia
        if abs(snapshot.bb_position) > 0.8 and snapshot.trend == "NEUTRAL":
            contradictions += 1
            total_pairs += 1
        
        if total_pairs == 0:
            return 0.0
        
        return contradictions / total_pairs
    
    def _detect_alerts(self, snapshot: TechnicalSnapshot, symbol: str) -> List[str]:
        """
        Detecta condiciones inusuales que merecen alerta.
        """
        alerts = []
        
        # 1. Sobrecompra/sobreventa extrema
        if snapshot.rsi < 20:
            alerts.append(f"RSI extremadamente bajo ({snapshot.rsi:.0f}) en {symbol}")
        elif snapshot.rsi > 80:
            alerts.append(f"RSI extremadamente alto ({snapshot.rsi:.0f}) en {symbol}")
        
        # 2. Volatilidad extrema
        if snapshot.volatility_value > 2.5:
            alerts.append(f"Volatilidad alta ({snapshot.volatility_value:.1f}%) - posible ruptura")
        
        # 3. Acumulación/Distribución
        if snapshot.volume_profile == "ACCUMULATION":
            alerts.append(f"Acumulación detectada en {symbol}")
        elif snapshot.volume_profile == "DISTRIBUTION":
            alerts.append(f"Distribución detectada en {symbol}")
        
        # 4. Divergencia
        if snapshot.divergence == "BULLISH":
            alerts.append(f"Divergencia alcista en {symbol} - posible reversión")
        elif snapshot.divergence == "BEARISH":
            alerts.append(f"Divergencia bajista en {symbol} - posible reversión")
        
        # 5. Bollinger squeeze
        if abs(snapshot.bb_position) > 0.9:
            alerts.append(f"Bollinger band cerca del extremo ({snapshot.bb_position:.2f}) - posible breakout")
        
        # 6. Patrón de vela significativo
        if snapshot.candle_pattern in ("BULLISH_ENGULFING", "BEARISH_ENGULFING"):
            alerts.append(f"Patrón {snapshot.candle_pattern} en {symbol}")
        elif snapshot.candle_pattern in ("HAMMER", "SHOOTING_STAR"):
            alerts.append(f"Posible reversión: {snapshot.candle_pattern} en {symbol}")
        
        return alerts
    
    def generate_trading_decision(self, df: pd.DataFrame, symbol: str) -> TradingDecision:
        """
        Genera decisión de trading basada en el análisis completo.
        Incorpora learnings de Signal Memory y régimen de mercado.
        """
        try:
            analysis = self.analyze_market(df, symbol)
            
            # ========== 1. VERIFICAR OVERRIDE DE MEMORIA ==========
            memory_override = self.memory_consultant.should_override_decision(
                symbol, analysis.trend, analysis.confidence
            )
            
            if memory_override:
                return TradingDecision(
                    signal=TradingSignal.HOLD,
                    confidence=0.3,
                    reasoning=f"HOLD por override de memoria: {memory_override}",
                    suggested_position_size=0.0,
                    stop_loss=0,
                    take_profit=0,
                    risk_reward_ratio=0,
                    time_horizon="INTRADAY",
                    urgency="LOW",
                    entry_price=df['close'].iloc[-1] if len(df) > 0 else 0,
                    regime=analysis.regime,
                    divergence=analysis.divergence,
                    market_regime_alignment=self._calculate_regime_alignment(analysis.trend, analysis.regime) if hasattr(analysis, 'regime') else 0.5
                )
            
            # ========== 2. DECIDIR SEÑAL ==========
            signal, confidence, reasoning = self._decide_signal(
                analysis, df
            )
            
            # ========== 3. CALCULAR NIVELES ==========
            entry_price = df['close'].iloc[-1] if len(df) > 0 else 0
            sl_price, tp_price, rr = self._calculate_trade_levels(
                entry_price, analysis, signal, df
            )
            
            # ========== 4. DETERMINAR URGENCIA Y HORIZONTE ==========
            urgency, time_horizon = self._determine_urgency(analysis, signal)
            
            # ========== 5. TAMAÑO DE POSICIÓN SUGERIDO ==========
            position_size = self._calculate_suggested_size(
                signal, analysis.confidence, analysis.regime
            )
            
            # ========== 6. CONSTRUIR DECISIÓN ==========
            decision = TradingDecision(
                signal=signal,
                confidence=confidence,
                reasoning=reasoning,
                suggested_position_size=position_size,
                stop_loss=sl_price,
                take_profit=tp_price,
                risk_reward_ratio=rr,
                time_horizon=time_horizon,
                urgency=urgency,
                entry_price=entry_price,
                regime=analysis.regime if hasattr(analysis, 'regime') else "UNKNOWN",
                divergence=analysis.divergence if hasattr(analysis, 'divergence') else "NONE",
                market_regime_alignment=self._calculate_regime_alignment(analysis.trend, analysis.regime) if hasattr(analysis, 'regime') else 0.5
            )
            
            self.decision_history.append(decision)
            
            # Limitar historial
            if len(self.decision_history) > 200:
                self.decision_history = self.decision_history[-200:]
            
            return decision
            
        except Exception as e:
            logger.error(f"Error generando decisión: {e}", exc_info=True)
            # Decisión segura por defecto
            return TradingDecision(
                signal=TradingSignal.HOLD,
                confidence=0.3,
                reasoning=f"HOLD por error: {str(e)[:100]}",
                suggested_position_size=0.0,
                stop_loss=0,
                take_profit=0,
                risk_reward_ratio=0,
                time_horizon="INTRADAY",
                urgency="LOW",
                entry_price=df['close'].iloc[-1] if len(df) > 0 else 0,
            )
    
    def _decide_signal(self, analysis: MarketAnalysis, df: pd.DataFrame) -> Tuple[TradingSignal, float, str]:
        """
        Lógica de decisión mejorada considerando:
        - Score técnico
        - Régimen de mercado
        - Divergencias
        - Volumen conviction
        - Patrones de velas
        """
        signal = TradingSignal.HOLD
        confidence = analysis.confidence
        reasons = []
        
        tech_score = analysis.technical_score
        
        # Extraer datos del análisis para decisión
        regime = getattr(analysis, 'regime', "UNKNOWN")
        divergence = getattr(analysis, 'divergence', "NONE")
        volume_profile = getattr(analysis, 'volume_profile', "NORMAL")
        trend = analysis.trend
        
        # ========== LÓGICA DE DECISIÓN ==========
        
        # Condiciones para COMPRA
        buy_conditions_met = 0
        buy_conditions_total = 0
        
        # Condición 1: Tendencia alcista + score técnico alto
        if trend == "BULLISH" and tech_score > 0.6:
            buy_conditions_met += 2
            reasons.append(f"Tendencia alcista (score: {tech_score:.2f})")
        buy_conditions_total += 2
        
        # Condición 2: Régimen favorable para compra
        if regime in ("MOMENTUM", "TRENDING_UP"):
            buy_conditions_met += 2
            reasons.append(f"Régimen favorable: {regime}")
        buy_conditions_total += 2
        
        # Condición 3: Divergencia alcista
        if divergence == "BULLISH":
            buy_conditions_met += 2
            reasons.append("Divergencia alcista detectada")
        buy_conditions_total += 2
        
        # Condición 4: RSI en sobreventa (en tendencia alcista)
        if hasattr(df, 'close') and len(df) > 14:
            rsi = TechnicalAnalysisEngine._calc_rsi(df['close'])
            if rsi < 30 and trend == "BULLISH":
                buy_conditions_met += 1
                reasons.append(f"RSI sobreventa ({rsi:.1f}) en tendencia alcista")
            buy_conditions_total += 1
        
        # Condición 5: Volumen alto (confirmación)
        if volume_profile in ("HIGH", "ACCUMULATION"):
            buy_conditions_met += 1
            reasons.append(f"Volumen: {volume_profile}")
        buy_conditions_total += 1
        
        # Condiciones para VENTA
        sell_conditions_met = 0
        sell_conditions_total = 0
        
        if trend == "BEARISH" and tech_score > 0.6:
            sell_conditions_met += 2
            reasons.append(f"Tendencia bajista (score: {tech_score:.2f})")
        sell_conditions_total += 2
        
        if regime in ("MOMENTUM", "TRENDING_DOWN"):
            sell_conditions_met += 2
            reasons.append(f"Régimen bajista: {regime}")
        sell_conditions_total += 2
        
        if divergence == "BEARISH":
            sell_conditions_met += 2
            reasons.append("Divergencia bajista detectada")
        sell_conditions_total += 2
        
        if hasattr(df, 'close') and len(df) > 14:
            rsi = TechnicalAnalysisEngine._calc_rsi(df['close'])
            if rsi > 70 and trend == "BEARISH":
                sell_conditions_met += 1
                reasons.append(f"RSI sobrecompra ({rsi:.1f}) en tendencia bajista")
            sell_conditions_total += 1
        
        if volume_profile in ("HIGH", "DISTRIBUTION"):
            sell_conditions_met += 1
            reasons.append(f"Volumen: {volume_profile}")
            if volume_profile == "DISTRIBUTION":
                sell_conditions_met += 1  # Distribución = más peso a venta
        sell_conditions_total += 1
        
        # ========== DECIDIR ==========
        
        buy_ratio = buy_conditions_met / max(buy_conditions_total, 1)
        sell_ratio = sell_conditions_met / max(sell_conditions_total, 1)
        
        min_threshold = self.config.get('min_confidence_threshold', 0.55)
        
        if buy_ratio > min_threshold and buy_ratio > sell_ratio * 1.3:
            signal = TradingSignal.BUY
            confidence = min(1.0, buy_ratio * analysis.confidence * 1.2)
            reasoning = "✅ COMPRA: " + " | ".join(reasons[:4])
        elif sell_ratio > min_threshold and sell_ratio > buy_ratio * 1.3:
            signal = TradingSignal.SELL
            confidence = min(1.0, sell_ratio * analysis.confidence * 1.2)
            reasoning = "❌ VENTA: " + " | ".join(reasons[:4])
        else:
            signal = TradingSignal.HOLD
            confidence = 0.4 + abs(buy_ratio - sell_ratio) * 0.3
            reasons.append(f"Señal insuficiente (buy:{buy_ratio:.2f} sell:{sell_ratio:.2f})")
            reasoning = "⏸️ HOLD: " + " | ".join(reasons[-3:])
        
        # Penalización si multi-timeframe no es coherente
        mrf = getattr(self, '_last_mrf_analysis', None)
        if mrf and not mrf.get('coherent', True) and signal != TradingSignal.HOLD:
            if mrf.get('coherence', 1.0) < self.config.get('signal_coherence_threshold', 0.5):
                confidence *= 0.8
                reasoning += " | ⚠️ Timeframes en conflicto"
        
        return signal, min(confidence, 1.0), reasoning
    
    def _calculate_trade_levels(self, entry_price: float, analysis: MarketAnalysis,
                                 signal: TradingSignal, df: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Calcula niveles de SL/TP basados en análisis técnico.
        """
        if signal == TradingSignal.HOLD:
            return 0, 0, 0
        
        is_buy = signal == TradingSignal.BUY
        
        # Obtener niveles clave
        support = analysis.key_levels.get('support', entry_price * 0.98)
        resistance = analysis.key_levels.get('resistance', entry_price * 1.02)
        
        # Calcular ATR si hay datos suficientes
        if len(df) > 14:
            atr = TechnicalAnalysisEngine._calc_atr_simple(df)
        else:
            atr = entry_price * 0.005  # 0.5% por defecto
        
        if is_buy:
            # SL: debajo de soporte o 2 ATRs
            sl_price = min(support, entry_price - 2 * atr)
            sl_price = max(sl_price, entry_price * 0.97)  # Max 3% loss
            
            # TP: en resistencia o 3 ATRs
            tp_price = max(resistance, entry_price + 3 * atr)
        else:
            # SL: arriba de resistencia o 2 ATRs
            sl_price = max(resistance, entry_price + 2 * atr)
            sl_price = min(sl_price, entry_price * 1.03)  # Max 3% loss
            
            # TP: en soporte o 3 ATRs
            tp_price = min(support, entry_price - 3 * atr)
        
        # Calcular R:R
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        rr = reward / risk if risk > 0 else 1.5
        
        return sl_price, tp_price, min(rr, 5.0)  # Cap en 5:1
    
    @staticmethod
    def _calc_atr_simple(df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ATR simple"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(period).mean().iloc[-1]
    
    def _calculate_suggested_size(self, signal: TradingSignal, confidence: float,
                                   regime: str) -> float:
        """
        Calcula tamaño de posición sugerido basado en:
        - Tipo de señal (BUY/SELL/HOLD)
        - Confianza
        - Régimen de mercado
        """
        if signal == TradingSignal.HOLD:
            return 0.0
        
        # Base: 10% del capital sugerido por trade
        base_size = 0.10
        
        # Ajuste por confianza
        size = base_size * confidence
        
        # Ajuste por régimen
        regime_multipliers = {
            'MOMENTUM': 1.3,
            'TRENDING_UP': 1.2,
            'TRENDING_DOWN': 1.2,
            'HIGH_IMPULSE': 1.1,
            'VOLATILE': 0.6,
            'LATERAL': 0.5,
            'LOW_LIQUIDITY': 0.3,
        }
        multiplier = regime_multipliers.get(regime, 0.8)
        size *= multiplier
        
        return min(max(size, 0.0), 0.25)  # 0% a 25%
    
    def _determine_urgency(self, analysis: MarketAnalysis, signal: TradingSignal) -> Tuple[str, str]:
        """
        Determina urgencia y horizonte temporal de la señal.
        """
        if signal == TradingSignal.HOLD:
            return "LOW", "INTRADAY"
        
        divergence = getattr(analysis, 'divergence', "NONE")
        regime = getattr(analysis, 'regime', "UNKNOWN")
        
        # Divergencias = alta urgencia
        if divergence != "NONE":
            urgency = "HIGH"
        elif analysis.volatility == "HIGH":
            urgency = "HIGH"
        elif analysis.confidence > 0.8:
            urgency = "MEDIUM"
        else:
            urgency = "MEDIUM"
        
        # Horizonte temporal
        if regime in ("MOMENTUM", "HIGH_IMPULSE"):
            horizon = "SCALP"
        elif analysis.trend in ("BULLISH", "BEARISH") and analysis.strength > 0.6:
            horizon = "INTRADAY"
        elif analysis.volatility == "LOW":
            horizon = "SWING"
        else:
            horizon = "INTRADAY"
        
        return urgency, horizon
    
    def get_market_context(self, symbol: str) -> Dict:
        """
        Obtiene contexto de mercado enriquecido para el orquestador.
        """
        try:
            # Buscar análisis reciente
            recent_analysis = None
            for analysis in reversed(self.analysis_history):
                if analysis.symbol == symbol:
                    recent_analysis = analysis
                    break
            
            if not recent_analysis:
                return {
                    'trend': 'UNKNOWN',
                    'confidence': 0.5,
                    'volatility': 'MEDIUM',
                    'timestamp': None,
                    'regime': 'UNKNOWN',
                    'alerts': []
                }
            
            # Buscar el último snapshot para este símbolo
            recent_snapshot = None
            for snap in reversed(self.snapshot_history):
                if snap.symbol == symbol:
                    recent_snapshot = snap
                    break
            
            context = {
                'trend': recent_analysis.trend,
                'confidence': recent_analysis.confidence,
                'volatility': recent_analysis.volatility,
                'strength': recent_analysis.strength,
                'reasoning': recent_analysis.reasoning,
                'timestamp': recent_analysis.timestamp.isoformat() if recent_analysis.timestamp else None,
                'technical_score': recent_analysis.technical_score,
                'regime': recent_analysis.regime if hasattr(recent_analysis, 'regime') else "UNKNOWN",
                'divergence': recent_analysis.divergence if hasattr(recent_analysis, 'divergence') else "NONE",
                'volume_profile': recent_analysis.volume_profile if hasattr(recent_analysis, 'volume_profile') else "NORMAL",
            }
            
            # Añadir datos del snapshot si existe
            if recent_snapshot:
                context.update({
                    'rsi': recent_snapshot.rsi,
                    'adx': recent_snapshot.adx,
                    'volume_ratio': recent_snapshot.volume_ratio,
                    'bb_position': recent_snapshot.bb_position,
                    'candle_pattern': recent_snapshot.candle_pattern,
                })
            
            # Añadir últimas alertas
            recent_alerts = [
                a for a in self.alert_history[-20:]
                if symbol in a.get('symbols', [])
            ]
            if recent_alerts:
                context['alerts'] = recent_alerts[-5:]
            else:
                context['alerts'] = []
            
            return context
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto: {e}")
            return {
                'trend': 'UNKNOWN', 
                'confidence': 0.5,
                'volatility': 'MEDIUM',
                'alerts': []
            }
    
    def get_regime_history(self) -> List[Dict]:
        """
        Obtiene historial de clasificaciones de régimen.
        Útil para el ciclo de inteligencia diaria.
        """
        history = []
        for i, (time, regime) in enumerate(self.regime_classifier.regime_history):
            conf = self.regime_classifier.confidence_history[i] if i < len(self.regime_classifier.confidence_history) else 0.5
            history.append({
                'timestamp': time.isoformat(),
                'regime': regime,
                'confidence': conf,
            })
        return history
    
    def get_performance_summary(self) -> Dict:
        """
        Retorna resumen de rendimiento del cerebro.
        Útil para el ciclo de inteligencia diaria (DAILY_INTEL.md).
        """
        total_analyses = len(self.analysis_history)
        total_decisions = len(self.decision_history)
        
        buy_signals = sum(1 for d in self.decision_history if d.signal == TradingSignal.BUY)
        sell_signals = sum(1 for d in self.decision_history if d.signal == TradingSignal.SELL)
        hold_signals = sum(1 for d in self.decision_history if d.signal == TradingSignal.HOLD)
        
        avg_confidence = sum(d.confidence for d in self.decision_history) / max(total_decisions, 1)
        
        # Distribución de regímenes
        regime_counts = {}
        for r in self.regime_classifier.regime_history:
            regime = r[1]
            regime_counts[regime] = regime_counts.get(regime, 0) + 1
        
        return {
            'total_analyses': total_analyses,
            'total_decisions': total_decisions,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'hold_signals': hold_signals,
            'avg_confidence': avg_confidence,
            'regime_distribution': regime_counts,
            'onnx_available': ONNX_AVAILABLE,
            'version': '3.0.0',
        }


# ==================== INSTANCIA GLOBAL ====================

_brain_instance = None

def Brain(*args, **kwargs):
    """
    Singleton factory para BrainClineModule.
    Si se pasa memory_module como kwarg, se lo pasa al módulo.
    """
    global _brain_instance
    if _brain_instance is None:
        memory_module = kwargs.get('memory_module', None)
        _brain_instance = BrainClineModule(memory_module=memory_module)
    return _brain_instance