"""
Módulo Cerebro Cline - v4.0 OPTIMIZADO
Mejoras implementadas:
1. Estrategia Breakout como tercer voto en el ensemble
2. Optimización walk-forward de parámetros (RSI, BB dinámicos)
3. Integración de modelo ONNX para predicción de precio
4. Sentimiento incorporado como factor en la decisión (no solo confianza)
5. Sistema de votos flexible (≥2 votos pero con pesos dinámicos)
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
sys.path.insert(0, str(Path(__file__).parent.parent / "python_brain"))
try:
    # Intentar importar pero manejar error gracefully
    import onnxruntime as ort
    ONNX_AVAILABLE = True
    logger.info("ONNX runtime disponible")
except ImportError:
    ONNX_AVAILABLE = False
    logger.warning("ONNX no disponible, usando métodos alternativos")

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
    HIGH_IMPULSE = "HIGH_IMPULSE"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"


class SentimentScore(Enum):
    """Niveles de sentimiento del mercado"""
    VERY_BEARISH = -2
    BEARISH = -1
    NEUTRAL = 0
    BULLISH = 1
    VERY_BULLISH = 2


@dataclass
class StrategyVote:
    """Voto individual de una estrategia"""
    strategy_name: str
    signal: TradingSignal
    confidence: float
    weight: float = 1.0  # Peso dinámico según performance histórico
    reasoning: str = ""


@dataclass
class WalkForwardParams:
    """Parámetros optimizados vía walk-forward"""
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    bb_period: int = 20
    bb_std: float = 2.0
    breakout_lookback: int = 20
    sentiment_weight: float = 0.3
    last_optimization: datetime = field(default_factory=datetime.now)
    optimization_score: float = 0.0


# ==================== ESTRATEGIA BREAKOUT ====================

class BreakoutStrategy:
    """
    Estrategia de breakout detection:
    - Detecta rupturas de rangos consolidados
    - Confirma con volumen
    - Genera señal de compra/venta en breakouts válidos
    """
    
    def __init__(self, lookback: int = 20, volume_threshold: float = 1.5):
        self.lookback = lookback
        self.volume_threshold = volume_threshold
        self.performance_history: List[float] = []
    
    def generate_signal(self, df: pd.DataFrame) -> StrategyVote:
        """
        Genera señal basada en breakout detection.
        Retorna: StrategyVote con señal, confianza y razonamiento
        """
        if df is None or len(df) < self.lookback + 10:
            return StrategyVote(
                strategy_name="breakout",
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning="Datos insuficientes para breakout"
            )
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df.get('volume', pd.Series([1] * len(df)))
        
        # Calcular rango de consolidación
        highest_high = high.rolling(self.lookback).max().iloc[-1]
        lowest_low = low.rolling(self.lookback).min().iloc[-1]
        range_size = highest_high - lowest_low
        
        if range_size == 0:
            return StrategyVote(
                strategy_name="breakout",
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning="Rango cero"
            )
        
        current_price = close.iloc[-1]
        prev_price = close.iloc[-2]
        
        # Volumen promedio
        vol_ma = volume.rolling(20).mean().iloc[-1]
        current_volume = volume.iloc[-1]
        volume_ratio = current_volume / vol_ma if vol_ma > 0 else 1.0
        
        # Detectar breakout alcista
        bullish_breakout = (
            current_price > highest_high and
            prev_price <= highest_high and
            volume_ratio >= self.volume_threshold * 0.8
        )
        
        # Detectar breakout bajista
        bearish_breakout = (
            current_price < lowest_low and
            prev_price >= lowest_low and
            volume_ratio >= self.volume_threshold * 0.8
        )
        
        # Breakout falso (sin volumen)
        false_breakout_up = current_price > highest_high and volume_ratio < 1.0
        false_breakout_down = current_price < lowest_low and volume_ratio < 1.0
        
        if bullish_breakout and not false_breakout_up:
            confidence = min(0.9, 0.5 + (volume_ratio - 1) * 0.2 + (range_size / current_price) * 10)
            return StrategyVote(
                strategy_name="breakout",
                signal=TradingSignal.BUY,
                confidence=confidence,
                weight=self._get_dynamic_weight(),
                reasoning=f"Breakout alcista confirmado (vol: {volume_ratio:.2f}x)"
            )
        elif bearish_breakout and not false_breakout_down:
            confidence = min(0.9, 0.5 + (volume_ratio - 1) * 0.2 + (range_size / current_price) * 10)
            return StrategyVote(
                strategy_name="breakout",
                signal=TradingSignal.SELL,
                confidence=confidence,
                weight=self._get_dynamic_weight(),
                reasoning=f"Breakout bajista confirmado (vol: {volume_ratio:.2f}x)"
            )
        elif false_breakout_up or false_breakout_down:
            return StrategyVote(
                strategy_name="breakout",
                signal=TradingSignal.HOLD,
                confidence=0.6,
                reasoning="Posible breakout falso (volumen bajo)"
            )
        else:
            # Precio dentro del rango
            position_in_range = (current_price - lowest_low) / range_size if range_size > 0 else 0.5
            if 0.3 < position_in_range < 0.7:
                return StrategyVote(
                    strategy_name="breakout",
                    signal=TradingSignal.HOLD,
                    confidence=0.7,
                    reasoning=f"En rango ({position_in_range:.2%})"
                )
            else:
                return StrategyVote(
                    strategy_name="breakout",
                    signal=TradingSignal.HOLD,
                    confidence=0.4,
                    reasoning="Cerca de límites del rango"
                )
    
    def _get_dynamic_weight(self) -> float:
        """Calcula peso dinámico basado en performance histórico"""
        if len(self.performance_history) < 5:
            return 1.0
        
        recent_performance = np.mean(self.performance_history[-10:])
        # Mapear performance [-0.1, 0.2] a weight [0.5, 1.5]
        weight = 1.0 + (recent_performance * 2)
        return max(0.5, min(1.5, weight))
    
    def record_trade_result(self, pnl_pct: float):
        """Registra resultado de trade para ajustar peso dinámico"""
        self.performance_history.append(pnl_pct)
        if len(self.performance_history) > 50:
            self.performance_history.pop(0)


# ==================== OPTIMIZACIÓN WALK-FORWARD ====================

class WalkForwardOptimizer:
    """
    Optimizador walk-forward para parámetros dinámicos:
    - Ajusta RSI period, overbought/oversold levels
    - Ajusta Bollinger Bands period y std multiplier
    - Re-optimiza cada N períodos o cuando cambia régimen
    """
    
    def __init__(self, optimization_window: int = 100, step_size: int = 20):
        self.optimization_window = optimization_window
        self.step_size = step_size
        self.current_params = WalkForwardParams()
        self.optimization_history: List[Dict] = []
    
    def optimize(self, df: pd.DataFrame, market_regime: str) -> WalkForwardParams:
        """
        Ejecuta optimización walk-forward sobre datos históricos.
        Busca mejores parámetros para el régimen actual.
        """
        if df is None or len(df) < self.optimization_window + 50:
            return self.current_params
        
        logger.info(f"Ejecutando walk-forward optimization (régimen: {market_regime})")
        
        best_score = -float('inf')
        best_params = self.current_params
        
        # Grid search sobre parámetros clave
        rsi_periods = [10, 12, 14, 16, 18]
        bb_stds = [1.5, 1.8, 2.0, 2.2, 2.5]
        
        # Ajustar búsqueda según régimen
        if market_regime in ["VOLATILE", "HIGH_IMPULSE"]:
            rsi_periods = [8, 10, 12, 14]  # RSI más rápido
            bb_stds = [2.2, 2.5, 2.8]  # Bandas más anchas
        elif market_regime in ["LATERAL", "LOW_LIQUIDITY"]:
            rsi_periods = [14, 16, 18, 20]  # RSI más lento
            bb_stds = [1.5, 1.8, 2.0]  # Bandas más estrechas
        
        for rsi_period in rsi_periods:
            for bb_std in bb_stds:
                score = self._evaluate_params(df, rsi_period, bb_std, market_regime)
                if score > best_score:
                    best_score = score
                    best_params = WalkForwardParams(
                        rsi_period=rsi_period,
                        rsi_overbought=70.0 if market_regime in ["TRENDING_UP", "MOMENTUM"] else 65.0,
                        rsi_oversold=30.0 if market_regime in ["TRENDING_DOWN", "MOMENTUM"] else 35.0,
                        bb_period=20,
                        bb_std=bb_std,
                        breakout_lookback=15 if market_regime in ["VOLATILE", "HIGH_IMPULSE"] else 20,
                        sentiment_weight=0.4 if market_regime in ["MOMENTUM", "TRENDING_UP", "TRENDING_DOWN"] else 0.2,
                        last_optimization=datetime.now(),
                        optimization_score=best_score
                    )
        
        # Guardar historial
        self.optimization_history.append({
            'timestamp': datetime.now(),
            'regime': market_regime,
            'params': best_params,
            'score': best_score
        })
        
        if len(self.optimization_history) > 20:
            self.optimization_history.pop(0)
        
        self.current_params = best_params
        logger.info(f"Walk-forward completo. Score: {best_score:.4f}")
        
        return best_params
    
    def _evaluate_params(self, df: pd.DataFrame, rsi_period: int, bb_std: float, 
                         regime: str) -> float:
        """
        Evalúa calidad de parámetros usando métricas simples.
        Retorna score combinado (Sharpe-like + win rate proxy)
        """
        close = df['close']
        
        # Calcular indicadores con parámetros candidatos
        rsi = self._calc_rsi(close, rsi_period)
        bb_mid = close.rolling(20).mean()
        bb_upper = bb_mid + bb_std * close.rolling(20).std()
        bb_lower = bb_mid - bb_std * close.rolling(20).std()
        
        # Simular señales simples
        signals = []
        for i in range(len(close) - 1):
            if rsi.iloc[i] < 35 and close.iloc[i] < bb_lower.iloc[i]:
                signals.append(1)  # Buy
            elif rsi.iloc[i] > 65 and close.iloc[i] > bb_upper.iloc[i]:
                signals.append(-1)  # Sell
            else:
                signals.append(0)  # Hold
        
        # Calcular retornos following señales
        returns = close.pct_change()
        strategy_returns = []
        
        for i, sig in enumerate(signals[:-1]):
            if sig != 0 and i + 1 < len(returns):
                strat_ret = sig * returns.iloc[i + 1]
                strategy_returns.append(strat_ret)
        
        if len(strategy_returns) < 10:
            return -float('inf')
        
        # Score: Sharpe-like ratio
        mean_ret = np.mean(strategy_returns)
        std_ret = np.std(strategy_returns)
        sharpe = mean_ret / std_ret if std_ret > 0 else 0
        
        # Win rate proxy
        wins = sum(1 for r in strategy_returns if r > 0)
        win_rate = wins / len(strategy_returns)
        
        # Score combinado
        score = sharpe * 0.6 + win_rate * 0.4
        
        return score
    
    def _calc_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcula RSI con período dinámico"""
        delta = prices.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))
    
    def should_reoptimize(self, current_regime: str, last_regime: str) -> bool:
        """Determina si se debe re-optimizar basado en cambio de régimen"""
        # Re-optimizar si cambió el régimen
        if current_regime != last_regime:
            return True
        
        # O si pasó mucho tiempo desde última optimización
        time_since_opt = datetime.now() - self.current_params.last_optimization
        return time_since_opt.total_seconds() > 3600  # 1 hora


# ==================== PREDICTOR ONNX DE PRECIOS ====================

class ONNXPricePredictorWrapper:
    """
    Wrapper para modelo ONNX de predicción de precios.
    Si no hay modelo ONNX disponible, usa fallback estadístico.
    """
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.fallback_active = False
        
        if ONNX_AVAILABLE and model_path and Path(model_path).exists():
            try:
                import onnxruntime as ort
                self.model = ort.InferenceSession(model_path)
                logger.info(f"Modelo ONNX cargado: {model_path}")
            except Exception as e:
                logger.warning(f"Error cargando ONNX: {e}. Usando fallback.")
                self.fallback_active = True
        else:
            logger.warning("ONNX no disponible. Usando predictor estadístico.")
            self.fallback_active = True
    
    def predict_direction(self, df: pd.DataFrame, horizon: int = 5) -> Tuple[str, float]:
        """
        Predice dirección del precio en próximo horizonte.
        Returns: (direction, confidence) donde direction ∈ ["UP", "DOWN", "NEUTRAL"]
        """
        if self.fallback_active or self.model is None:
            return self._statistical_prediction(df, horizon)
        
        try:
            # Preparar features para el modelo
            features = self._extract_features(df)
            
            # Ejecutar inferencia
            input_name = self.model.get_inputs()[0].name
            output_name = self.model.get_outputs()[0].name
            
            prediction = self.model.run([output_name], {input_name: features.astype(np.float32)})[0]
            
            # Interpretar predicción
            if len(prediction.shape) > 1:
                probabilities = prediction[0]
                direction_idx = np.argmax(probabilities)
                confidence = probabilities[direction_idx]
            else:
                direction_idx = 0 if prediction[0] > 0.5 else 1
                confidence = abs(prediction[0] - 0.5) * 2
            
            directions = ["UP", "DOWN", "NEUTRAL"]
            direction = directions[min(direction_idx, 2)]
            
            return direction, float(confidence)
            
        except Exception as e:
            logger.error(f"Error en predicción ONNX: {e}")
            self.fallback_active = True
            return self._statistical_prediction(df, horizon)
    
    def _statistical_prediction(self, df: pd.DataFrame, horizon: int) -> Tuple[str, float]:
        """
        Fallback estadístico cuando ONNX no está disponible.
        Usa combinación de momentum y mean reversion.
        """
        if df is None or len(df) < 50:
            return "NEUTRAL", 0.3
        
        close = df['close']
        
        # Momentum a corto plazo
        momentum_5 = close.pct_change(5).iloc[-1]
        momentum_10 = close.pct_change(10).iloc[-1]
        
        # Mean reversion (desviación de media móvil)
        ma_20 = close.rolling(20).mean().iloc[-1]
        deviation = (close.iloc[-1] - ma_20) / ma_20
        
        # Volatilidad ajustada
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        
        # Score combinado
        momentum_score = (momentum_5 + momentum_10 * 0.5) / 1.5
        mr_score = -deviation * 2  # Mean reversion: negativo si está arriba
        
        # Ponderar según volatilidad
        if volatility > 0.03:
            # Alta volatilidad: más peso a momentum
            combined_score = momentum_score * 0.7 + mr_score * 0.3
        else:
            # Baja volatilidad: más peso a mean reversion
            combined_score = momentum_score * 0.3 + mr_score * 0.7
        
        # Determinar dirección
        threshold = 0.005  # 0.5%
        if combined_score > threshold:
            direction = "UP"
            confidence = min(0.9, 0.5 + abs(combined_score) * 10)
        elif combined_score < -threshold:
            direction = "DOWN"
            confidence = min(0.9, 0.5 + abs(combined_score) * 10)
        else:
            direction = "NEUTRAL"
            confidence = 0.5 - abs(combined_score) * 5
        
        return direction, max(0.3, min(0.9, confidence))
    
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """Extrae features para el modelo ONNX"""
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df.get('volume', pd.Series([1] * len(df))).values
        
        features = []
        
        # Retornos
        for lag in [1, 2, 3, 5, 10]:
            ret = np.diff(close, lag) / close[:-lag]
            features.extend(ret[-10:] if len(ret) >= 10 else list(ret) + [0] * (10 - len(ret)))
        
        # Media móvil ratios
        for window in [5, 10, 20, 50]:
            ma = pd.Series(close).rolling(window).mean().values
            ratio = close / ma
            features.extend(ratio[-5:] if len(ratio) >= 5 else list(ratio) + [0] * (5 - len(ratio)))
        
        # Volatilidad
        vol = pd.Series(close).pct_change().rolling(10).std().values
        features.extend(vol[-5:] if len(vol) >= 5 else list(vol) + [0] * (5 - len(vol)))
        
        # Volumen relativo
        vol_ma = pd.Series(volume).rolling(20).mean().values
        vol_ratio = volume / vol_ma
        features.extend(vol_ratio[-5:] if len(vol_ratio) >= 5 else list(vol_ratio) + [0] * (5 - len(vol_ratio)))
        
        # Normalizar
        features = np.array(features[:100])  # Limitar a 100 features
        features = (features - np.mean(features)) / (np.std(features) + 1e-10)
        
        return features.reshape(1, -1)


# ==================== MOTOR DE ANÁLISIS DE SENTIMIENTO ====================

class SentimentAnalyzer:
    """
    Analizador de sentimiento que incorpora múltiples fuentes:
    - Noticias/crypto Twitter (simulado)
    - Fear & Greed Index
    - Social volume
    - Orden flow (si disponible)
    
    El sentimiento AHORA genera señales, no solo ajusta confianza.
    """
    
    def __init__(self):
        self.sentiment_history: List[Tuple[datetime, SentimentScore]] = []
        self.news_buffer: List[Dict] = []
    
    def analyze_sentiment(self, symbol: str, df: pd.DataFrame, 
                          external_data: Optional[Dict] = None) -> Tuple[SentimentScore, float, str]:
        """
        Analiza sentimiento del mercado.
        Returns: (sentiment_score, confidence, reasoning)
        """
        scores = []
        reasons = []
        
        # 1. Análisis técnico-based sentiment (price action)
        tech_sentiment, tech_conf = self._analyze_price_sentiment(df)
        scores.append((tech_sentiment, tech_conf))
        reasons.append(f"Price action: {tech_sentiment.name}")
        
        # 2. Volumen-based sentiment
        vol_sentiment, vol_conf = self._analyze_volume_sentiment(df)
        scores.append((vol_sentiment, vol_conf))
        reasons.append(f"Volume profile: {vol_sentiment.name}")
        
        # 3. External data (noticias, social, fear&greed)
        if external_data:
            ext_sentiment, ext_conf = self._analyze_external_sentiment(external_data)
            scores.append((ext_sentiment, ext_conf))
            reasons.append(f"External factors: {ext_sentiment.name}")
        else:
            # Sin datos externos, usar neutral con baja confianza
            scores.append((SentimentScore.NEUTRAL, 0.3))
            reasons.append("Sin datos externos")
        
        # Combinar scores ponderados
        total_weight = sum(conf for _, conf in scores)
        weighted_sum = sum(score.value * conf for score, conf in scores)
        
        combined_score_value = weighted_sum / total_weight if total_weight > 0 else 0
        
        # Mapear a SentimentScore
        if combined_score_value >= 1.5:
            final_sentiment = SentimentScore.VERY_BULLISH
        elif combined_score_value >= 0.5:
            final_sentiment = SentimentScore.BULLISH
        elif combined_score_value >= -0.5:
            final_sentiment = SentimentScore.NEUTRAL
        elif combined_score_value >= -1.5:
            final_sentiment = SentimentScore.BEARISH
        else:
            final_sentiment = SentimentScore.VERY_BEARISH
        
        # Confianza combinada
        avg_confidence = np.mean([conf for _, conf in scores])
        
        # Guardar historial
        self.sentiment_history.append((datetime.now(), final_sentiment))
        if len(self.sentiment_history) > 50:
            self.sentiment_history.pop(0)
        
        reasoning = " | ".join(reasons)
        
        return final_sentiment, avg_confidence, reasoning
    
    def _analyze_price_sentiment(self, df: pd.DataFrame) -> Tuple[SentimentScore, float]:
        """Analiza sentimiento basado en price action"""
        if df is None or len(df) < 20:
            return SentimentScore.NEUTRAL, 0.3
        
        close = df['close']
        
        # Tendencia reciente
        returns_5 = close.pct_change(5).iloc[-1]
        returns_10 = close.pct_change(10).iloc[-1]
        
        # Posición relativa a máximos/mínimos recientes
        high_20 = df['high'].rolling(20).max().iloc[-1]
        low_20 = df['low'].rolling(20).min().iloc[-1]
        position = (close.iloc[-1] - low_20) / (high_20 - low_20) if high_20 != low_20 else 0.5
        
        # Score
        score = 0
        if returns_5 > 0.02 and returns_10 > 0.03:
            score += 2
        elif returns_5 > 0.01:
            score += 1
        elif returns_5 < -0.02 and returns_10 < -0.03:
            score -= 2
        elif returns_5 < -0.01:
            score -= 1
        
        if position > 0.8:
            score += 1
        elif position < 0.2:
            score -= 1
        
        # Mapear a SentimentScore
        if score >= 2:
            sentiment = SentimentScore.VERY_BULLISH
        elif score >= 1:
            sentiment = SentimentScore.BULLISH
        elif score <= -2:
            sentiment = SentimentScore.VERY_BEARISH
        elif score <= -1:
            sentiment = SentimentScore.BEARISH
        else:
            sentiment = SentimentScore.NEUTRAL
        
        confidence = min(0.9, 0.5 + abs(score) * 0.1)
        
        return sentiment, confidence
    
    def _analyze_volume_sentiment(self, df: pd.DataFrame) -> Tuple[SentimentScore, float]:
        """Analiza sentimiento basado en volumen"""
        if df is None or 'volume' not in df.columns or len(df) < 20:
            return SentimentScore.NEUTRAL, 0.3
        
        volume = df['volume']
        close = df['close']
        
        vol_ma = volume.rolling(20).mean().iloc[-1]
        current_vol = volume.iloc[-1]
        vol_ratio = current_vol / vol_ma if vol_ma > 0 else 1.0
        
        # Dirección del precio con volumen alto
        price_change = close.iloc[-1] - close.iloc[-5]
        
        if vol_ratio > 2.0 and price_change > 0:
            return SentimentScore.VERY_BULLISH, 0.8
        elif vol_ratio > 2.0 and price_change < 0:
            return SentimentScore.VERY_BEARISH, 0.8
        elif vol_ratio > 1.5 and price_change > 0:
            return SentimentScore.BULLISH, 0.6
        elif vol_ratio > 1.5 and price_change < 0:
            return SentimentScore.BEARISH, 0.6
        else:
            return SentimentScore.NEUTRAL, 0.4
    
    def _analyze_external_sentiment(self, external_data: Dict) -> Tuple[SentimentScore, float]:
        """Analiza sentimiento de fuentes externas"""
        # Fear & Greed Index (0-100)
        fng = external_data.get('fear_greed_index', 50)
        if fng >= 75:
            fng_sentiment = SentimentScore.VERY_BULLISH
        elif fng >= 60:
            fng_sentiment = SentimentScore.BULLISH
        elif fng <= 25:
            fng_sentiment = SentimentScore.VERY_BEARISH
        elif fng <= 40:
            fng_sentiment = SentimentScore.BEARISH
        else:
            fng_sentiment = SentimentScore.NEUTRAL
        
        # Social volume (positivo/negativo)
        social_ratio = external_data.get('social_sentiment_ratio', 1.0)
        if social_ratio > 2.0:
            social_sentiment = SentimentScore.VERY_BULLISH
        elif social_ratio > 1.3:
            social_sentiment = SentimentScore.BULLISH
        elif social_ratio < 0.5:
            social_sentiment = SentimentScore.VERY_BEARISH
        elif social_ratio < 0.77:
            social_sentiment = SentimentScore.BEARISH
        else:
            social_sentiment = SentimentScore.NEUTRAL
        
        # Promediar
        avg_value = (fng_sentiment.value + social_sentiment.value) / 2
        
        if avg_value >= 1.5:
            sentiment = SentimentScore.VERY_BULLISH
        elif avg_value >= 0.5:
            sentiment = SentimentScore.BULLISH
        elif avg_value <= -1.5:
            sentiment = SentimentScore.VERY_BEARISH
        elif avg_value <= -0.5:
            sentiment = SentimentScore.BEARISH
        else:
            sentiment = SentimentScore.NEUTRAL
        
        confidence = 0.7  # Confianza moderada en datos externos
        
        return sentiment, confidence
    
    def get_sentiment_signal(self, sentiment: SentimentScore) -> Optional[TradingSignal]:
        """
        Convierte sentimiento extremo en señal de trading.
        Sentimientos muy extremos pueden generar señales contrarias (contrarian).
        """
        if sentiment == SentimentScore.VERY_BULLISH:
            # Extremo de optimismo = posible reversión (señal de venta contrarian)
            return TradingSignal.SELL
        elif sentiment == SentimentScore.VERY_BEARISH:
            # Extremo de pesimismo = posible reversión (señal de compra contrarian)
            return TradingSignal.BUY
        elif sentiment == SentimentScore.BULLISH:
            # Confirmar tendencia alcista
            return TradingSignal.BUY
        elif sentiment == SentimentScore.BEARISH:
            # Confirmar tendencia bajista
            return TradingSignal.SELL
        else:
            return None  # Neutral no genera señal


# ==================== CLASE PRINCIPAL CLINE BRAIN OPTIMIZADO ====================

class ClineBrainOptimized:
    """
    Cerebro Cline v4.0 con mejoras:
    1. Ensemble con 3 estrategias (mean reversion, momentum, breakout)
    2. Parámetros dinámicos vía walk-forward optimization
    3. Predictor ONNX integrado
    4. Sentimiento como factor generador de señales
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Inicializar componentes
        self.breakout_strategy = BreakoutStrategy(
            lookback=self.config.get('breakout_lookback', 20),
            volume_threshold=self.config.get('volume_threshold', 1.5)
        )
        
        self.walk_forward_optimizer = WalkForwardOptimizer(
            optimization_window=self.config.get('wf_window', 100),
            step_size=self.config.get('wf_step', 20)
        )
        
        onnx_model_path = self.config.get('onnx_model_path')
        self.onnx_predictor = ONNXPricePredictorWrapper(onnx_model_path)
        
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Estado
        self.current_params = WalkForwardParams()
        self.last_regime = "UNKNOWN"
        self.decision_history: List[Any] = []
    
    def analyze_and_decide(self, df: pd.DataFrame, symbol: str,
                           external_sentiment: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Pipeline completo de análisis y decisión.
        Returns: dict con señal, confianza, razonamiento, niveles, etc.
        """
        # 1. Optimizar parámetros si es necesario
        regime = self._quick_regime_detect(df)
        if self.walk_forward_optimizer.should_reoptimize(regime, self.last_regime):
            self.current_params = self.walk_forward_optimizer.optimize(df, regime)
            self.last_regime = regime
        
        # 2. Obtener predicción ONNX
        onnx_direction, onnx_confidence = self.onnx_predictor.predict_direction(df, horizon=5)
        
        # 3. Analizar sentimiento
        sentiment, sentiment_conf, sentiment_reasoning = self.sentiment_analyzer.analyze_sentiment(
            symbol, df, external_sentiment
        )
        sentiment_signal = self.sentiment_analyzer.get_sentiment_signal(sentiment)
        
        # 4. Generar votos de estrategias
        votes: List[StrategyVote] = []
        
        # Voto 1: Mean Reversion (con parámetros optimizados)
        mr_vote = self._generate_mean_reversion_vote(df)
        votes.append(mr_vote)
        
        # Voto 2: Momentum
        mom_vote = self._generate_momentum_vote(df)
        votes.append(mom_vote)
        
        # Voto 3: Breakout (nuevo!)
        breakout_vote = self.breakout_strategy.generate_signal(df)
        votes.append(breakout_vote)
        
        # Voto 4: ONNX Prediction (si tiene confianza suficiente)
        if onnx_confidence > 0.6:
            onnx_signal = TradingSignal.BUY if onnx_direction == "UP" else \
                         TradingSignal.SELL if onnx_direction == "DOWN" else None
            if onnx_signal:
                votes.append(StrategyVote(
                    strategy_name="onnx_predictor",
                    signal=onnx_signal,
                    confidence=onnx_confidence,
                    weight=1.2,  # Peso extra para ML
                    reasoning=f"Predicción ONNX: {onnx_direction} ({onnx_confidence:.2%})"
                ))
        
        # Voto 5: Sentiment (si genera señal)
        if sentiment_signal and sentiment_conf > 0.5:
            votes.append(StrategyVote(
                strategy_name="sentiment",
                signal=sentiment_signal,
                confidence=sentiment_conf,
                weight=self.current_params.sentiment_weight,
                reasoning=f"Sentimiento: {sentiment.name}"
            ))
        
        # 5. Agregar votos ponderados
        final_signal, final_confidence, reasoning = self._aggregate_votes(votes)
        
        # 6. Calcular niveles de entrada/salida
        entry_price = df['close'].iloc[-1] if len(df) > 0 else 0
        sl, tp, rr = self._calculate_levels(df, final_signal, entry_price)
        
        # 7. Construir resultado
        result = {
            'signal': final_signal.value if final_signal else 'HOLD',
            'confidence': final_confidence,
            'reasoning': reasoning,
            'entry_price': entry_price,
            'stop_loss': sl,
            'take_profit': tp,
            'risk_reward': rr,
            'votes': [(v.strategy_name, v.signal.value, v.confidence, v.weight) for v in votes],
            'market_regime': regime,
            'sentiment': sentiment.name,
            'onnx_prediction': onnx_direction,
            'optimized_params': {
                'rsi_period': self.current_params.rsi_period,
                'bb_std': self.current_params.bb_std,
                'breakout_lookback': self.current_params.breakout_lookback
            }
        }
        
        self.decision_history.append(result)
        if len(self.decision_history) > 100:
            self.decision_history.pop(0)
        
        return result
    
    def _generate_mean_reversion_vote(self, df: pd.DataFrame) -> StrategyVote:
        """Genera voto de estrategia mean reversion con parámetros optimizados"""
        if df is None or len(df) < 50:
            return StrategyVote("mean_reversion", TradingSignal.HOLD, 0.0, 1.0, "Datos insuficientes")
        
        close = df['close']
        params = self.current_params
        
        # Calcular RSI con parámetros optimizados
        rsi = self._calc_rsi_dynamic(close, params.rsi_period)
        
        # Calcular Bollinger con parámetros optimizados
        bb_mid = close.rolling(params.bb_period).mean()
        bb_std = close.rolling(params.bb_period).std()
        bb_upper = bb_mid + params.bb_std * bb_std
        bb_lower = bb_mid - params.bb_std * bb_std
        
        current_price = close.iloc[-1]
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50
        
        # Señales
        if current_rsi < params.rsi_oversold and current_price < bb_lower.iloc[-1]:
            confidence = min(0.9, (params.rsi_oversold - current_rsi) / 40 + 0.5)
            return StrategyVote(
                strategy_name="mean_reversion",
                signal=TradingSignal.BUY,
                confidence=confidence,
                weight=1.0,
                reasoning=f"RSI({params.rsi_period})={current_rsi:.1f} < {params.rsi_oversold}, precio < BB lower"
            )
        elif current_rsi > params.rsi_overbought and current_price > bb_upper.iloc[-1]:
            confidence = min(0.9, (current_rsi - params.rsi_overbought) / 40 + 0.5)
            return StrategyVote(
                strategy_name="mean_reversion",
                signal=TradingSignal.SELL,
                confidence=confidence,
                weight=1.0,
                reasoning=f"RSI({params.rsi_period})={current_rsi:.1f} > {params.rsi_overbought}, precio > BB upper"
            )
        else:
            return StrategyVote(
                strategy_name="mean_reversion",
                signal=TradingSignal.HOLD,
                confidence=0.5,
                weight=1.0,
                reasoning=f"RSI={current_rsi:.1f}, en rango normal"
            )
    
    def _generate_momentum_vote(self, df: pd.DataFrame) -> StrategyVote:
        """Genera voto de estrategia momentum"""
        if df is None or len(df) < 30:
            return StrategyVote("momentum", TradingSignal.HOLD, 0.0, 1.0, "Datos insuficientes")
        
        close = df['close']
        
        # Momentum indicators
        roc_5 = close.pct_change(5).iloc[-1]
        roc_10 = close.pct_change(10).iloc[-1]
        
        # EMA crossover
        ema_9 = pd.Series(close).ewm(span=9).mean()
        ema_21 = pd.Series(close).ewm(span=21).mean()
        
        current_price = close.iloc[-1]
        
        # Señales
        if roc_5 > 0.02 and roc_10 > 0.03 and ema_9.iloc[-1] > ema_21.iloc[-1]:
            confidence = min(0.9, 0.5 + roc_5 * 10)
            return StrategyVote(
                strategy_name="momentum",
                signal=TradingSignal.BUY,
                confidence=confidence,
                weight=1.1,
                reasoning=f"Momentum fuerte: ROC5={roc_5*100:.1f}%, EMA9>EMA21"
            )
        elif roc_5 < -0.02 and roc_10 < -0.03 and ema_9.iloc[-1] < ema_21.iloc[-1]:
            confidence = min(0.9, 0.5 + abs(roc_5) * 10)
            return StrategyVote(
                strategy_name="momentum",
                signal=TradingSignal.SELL,
                confidence=confidence,
                weight=1.1,
                reasoning=f"Momentum negativo: ROC5={roc_5*100:.1f}%, EMA9<EMA21"
            )
        else:
            return StrategyVote(
                strategy_name="momentum",
                signal=TradingSignal.HOLD,
                confidence=0.5,
                weight=1.0,
                reasoning=f"Momentum débil: ROC5={roc_5*100:.1f}%"
            )
    
    def _aggregate_votes(self, votes: List[StrategyVote]) -> Tuple[TradingSignal, float, str]:
        """
        Agrega votos ponderados para decisión final.
        Mejora: sistema flexible que permite señales con ≥2 votos ponderados.
        """
        if not votes:
            return TradingSignal.HOLD, 0.3, "Sin votos"
        
        # Calcular scores ponderados por señal
        buy_score = 0.0
        sell_score = 0.0
        total_weight = 0.0
        
        reasons = []
        
        for vote in votes:
            weight = vote.weight * vote.confidence
            total_weight += weight
            
            if vote.signal == TradingSignal.BUY:
                buy_score += weight
            elif vote.signal == TradingSignal.SELL:
                sell_score += weight
            
            reasons.append(f"{vote.strategy_name}: {vote.signal.value} ({vote.confidence:.2f}, w={vote.weight})")
        
        # Normalizar scores
        if total_weight > 0:
            buy_score /= total_weight
            sell_score /= total_weight
        
        # Threshold dinámico basado en número de votos
        num_votes = len(votes)
        min_threshold = 0.35 if num_votes >= 4 else 0.4  # Más flexibilidad con más votos
        
        # Decidir
        if buy_score > min_threshold and buy_score > sell_score * 1.2:
            signal = TradingSignal.BUY
            confidence = min(0.95, buy_score * 1.3)
            reasoning = f"✅ COMPRA: {' | '.join(reasons)}"
        elif sell_score > min_threshold and sell_score > buy_score * 1.2:
            signal = TradingSignal.SELL
            confidence = min(0.95, sell_score * 1.3)
            reasoning = f"❌ VENTA: {' | '.join(reasons)}"
        else:
            signal = TradingSignal.HOLD
            confidence = 0.4 + abs(buy_score - sell_score) * 0.3
            reasoning = f"⏸️ HOLD: {' | '.join(reasons)}"
        
        return signal, confidence, reasoning
    
    def _calculate_levels(self, df: pd.DataFrame, signal: TradingSignal, 
                          entry_price: float) -> Tuple[float, float, float]:
        """Calcula stop loss y take profit"""
        if signal == TradingSignal.HOLD or entry_price == 0:
            return 0, 0, 0
        
        # ATR para stops dinámicos
        if len(df) > 14:
            atr = self._calc_atr(df)
        else:
            atr = entry_price * 0.01
        
        if signal == TradingSignal.BUY:
            sl = entry_price - 2 * atr
            tp = entry_price + 3 * atr
        else:
            sl = entry_price + 2 * atr
            tp = entry_price - 3 * atr
        
        # Ajustar a porcentajes razonables
        sl = max(sl, entry_price * 0.97) if signal == TradingSignal.BUY else min(sl, entry_price * 1.03)
        
        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)
        rr = reward / risk if risk > 0 else 1.5
        
        return sl, tp, min(rr, 5.0)
    
    def _quick_regime_detect(self, df: pd.DataFrame) -> str:
        """Detección rápida de régimen de mercado"""
        if df is None or len(df) < 50:
            return "UNKNOWN"
        
        close = df['close']
        
        # Volatilidad
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        
        # Tendencia
        ma_20 = close.rolling(20).mean().iloc[-1]
        ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma_20
        
        if volatility > 0.03:
            return "VOLATILE"
        elif close.iloc[-1] > ma_20 > ma_50:
            return "TRENDING_UP"
        elif close.iloc[-1] < ma_20 < ma_50:
            return "TRENDING_DOWN"
        else:
            return "LATERAL"
    
    def _calc_rsi_dynamic(self, prices: pd.Series, period: int) -> pd.Series:
        """Calcula RSI con período dinámico"""
        delta = prices.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, 1e-10)
        return 100 - (100 / (1 + rs))
    
    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = (high - close.shift()).abs()
        tr3 = (low - close.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        return tr.rolling(period).mean().iloc[-1]


# ==================== FUNCIÓN DE EJEMPLO ====================

def test_optimized_brain():
    """Test rápido del cerebro optimizado"""
    import numpy as np
    
    # Datos sintéticos
    np.random.seed(42)
    n = 200
    prices = [100]
    for i in range(n-1):
        ret = np.random.normal(0.001, 0.02)
        prices.append(prices[-1] * (1 + ret))
    
    df = pd.DataFrame({
        'close': prices,
        'high': np.array(prices) * 1.01,
        'low': np.array(prices) * 0.99,
        'volume': np.random.randint(1000, 10000, n)
    })
    
    # Inicializar cerebro optimizado
    brain = ClineBrainOptimized(config={
        'breakout_lookback': 20,
        'volume_threshold': 1.5,
        'wf_window': 100,
        'wf_step': 20
    })
    
    # Ejecutar análisis
    result = brain.analyze_and_decide(df, 'BTC/USDT')
    
    print("=" * 70)
    print("🧠 CLINE BRAIN v4.0 OPTIMIZED - RESULTADO")
    print("=" * 70)
    print(f"Señal: {result['signal']}")
    print(f"Confianza: {result['confidence']:.2%}")
    print(f"Régimen: {result['market_regime']}")
    print(f"Sentimiento: {result['sentiment']}")
    print(f"Predicción ONNX: {result['onnx_prediction']}")
    print(f"Parámetros optimizados:")
    print(f"  - RSI Period: {result['optimized_params']['rsi_period']}")
    print(f"  - BB Std: {result['optimized_params']['bb_std']}")
    print(f"  - Breakout Lookback: {result['optimized_params']['breakout_lookback']}")
    print(f"\nVotos:")
    for vote in result['votes']:
        print(f"  - {vote[0]}: {vote[1]} (conf: {vote[2]:.2f}, weight: {vote[3]})")
    print(f"\nRazonamiento: {result['reasoning'][:200]}...")
    print(f"\nNiveles:")
    print(f"  - Entrada: ${result['entry_price']:.2f}")
    print(f"  - Stop Loss: ${result['stop_loss']:.2f}")
    print(f"  - Take Profit: ${result['take_profit']:.2f}")
    print(f"  - Risk/Reward: {result['risk_reward']:.2f}")
    print("=" * 70)
    
    return result


if __name__ == "__main__":
    test_optimized_brain()
