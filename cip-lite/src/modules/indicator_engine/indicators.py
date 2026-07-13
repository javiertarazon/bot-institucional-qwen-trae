"""
Módulo de Indicadores Técnicos - v2.0
Indicadores tradicionales + personalizados + combinaciones
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog

logger = structlog.get_logger()


@dataclass
class IndicatorResult:
    """Resultado de un indicador"""
    name: str
    value: float
    signal: str  # BUY, SELL, NEUTRAL
    confidence: float


class IndicatorEngine:
    """
    Motor de cálculo de indicadores técnicos
    Soporta indicadores tradicionales y personalizados
    """
    
    def __init__(self):
        self.indicators_registry = {
            # Tendencia
            'sma': self._calc_sma,
            'ema': self._calc_ema,
            'wma': self._calc_wma,
            'macd': self._calc_macd,
            'adx': self._calc_adx,
            
            # Volatilidad
            'atr': self._calc_atr,
            'bollinger': self._calc_bollinger,
            'keltner': self._calc_keltner,
            
            # Momentum
            'rsi': self._calc_rsi,
            'stochastic': self._calc_stochastic,
            'cci': self._calc_cci,
            'momentum': self._calc_momentum,
            'roc': self._calc_roc,
            
            # Volumen
            'obv': self._calc_obv,
            'volume_profile': self._calc_volume_profile,
            'mfi': self._calc_mfi
        }
        
        logger.info("Indicator Engine v2.0 inicializado")
    
    def calculate(self, df: pd.DataFrame, indicator_name: str, 
                  params: Dict = None) -> Optional[IndicatorResult]:
        """
        Calcula un indicador específico
        """
        if indicator_name not in self.indicators_registry:
            logger.error(f"Indicador desconocido: {indicator_name}")
            return None
        
        try:
            result = self.indicators_registry[indicator_name](df, params or {})
            return result
        except Exception as e:
            logger.error(f"Error calculando {indicator_name}: {e}")
            return None
    
    def calculate_all(self, df: pd.DataFrame, symbol: str) -> Dict[str, float]:
        """
        Calcula todos los indicadores disponibles
        Retorna dict con valores numéricos
        """
        results = {}
        
        for name, func in self.indicators_registry.items():
            try:
                result = func(df, {})
                if result:
                    results[name] = result.value
            except Exception as e:
                logger.warning(f"Error en {name}: {e}")
        
        return results
    
    def combine_indicators(self, df: pd.DataFrame, 
                          combinations: List[Dict]) -> List[IndicatorResult]:
        """
        Combina múltiples indicadores para generar señales compuestas
        combinations: [
            {'type': 'AND', 'indicators': ['rsi', 'macd']},
            {'type': 'OR', 'indicators': ['sma_cross', 'bollinger']}
        ]
        """
        results = []
        
        for combo in combinations:
            signals = []
            confidences = []
            
            for ind_name in combo['indicators']:
                result = self.calculate(df, ind_name)
                if result:
                    signals.append(result.signal)
                    confidences.append(result.confidence)
            
            # Combinar señales
            if combo['type'] == 'AND':
                final_signal = 'BUY' if all(s == 'BUY' for s in signals) else \
                              'SELL' if all(s == 'SELL' for s in signals) else 'NEUTRAL'
            else:  # OR
                final_signal = 'BUY' if 'BUY' in signals else \
                              'SELL' if 'SELL' in signals else 'NEUTRAL'
            
            avg_confidence = np.mean(confidences) if confidences else 0.0
            
            results.append(IndicatorResult(
                name=f"combo_{combo['type']}_{'_'.join(combo['indicators'])}",
                value=avg_confidence,
                signal=final_signal,
                confidence=avg_confidence
            ))
        
        return results
    
    def generate_signal(self, df: pd.DataFrame, rule_set: Dict) -> IndicatorResult:
        """
        Genera señal basada en reglas personalizadas
        rule_set: {
            'conditions': [
                {'indicator': 'rsi', 'operator': '<', 'value': 30},
                {'indicator': 'macd', 'operator': '>', 'value': 0}
            ],
            'logic': 'AND'  # o 'OR'
        }
        """
        conditions_met = []
        
        for condition in rule_set.get('conditions', []):
            ind_name = condition['indicator']
            operator = condition['operator']
            threshold = condition['value']
            
            result = self.calculate(df, ind_name)
            if not result:
                continue
            
            actual = result.value
            met = False
            
            if operator == '<' and actual < threshold:
                met = True
            elif operator == '>' and actual > threshold:
                met = True
            elif operator == '==' and actual == threshold:
                met = True
            elif operator == '!=' and actual != threshold:
                met = True
            
            conditions_met.append(met)
        
        # Evaluar lógica
        logic = rule_set.get('logic', 'AND')
        final_signal = 'NEUTRAL'
        
        if logic == 'AND' and all(conditions_met):
            final_signal = 'BUY'
        elif logic == 'OR' and any(conditions_met):
            final_signal = 'BUY'
        elif logic == 'NOT' and not any(conditions_met):
            final_signal = 'SELL'
        
        return IndicatorResult(
            name='custom_rule',
            value=1.0 if final_signal != 'NEUTRAL' else 0.0,
            signal=final_signal,
            confidence=1.0 if final_signal != 'NEUTRAL' else 0.0
        )
    
    # ========== INDICADORES TRADICIONALES ==========
    
    def _calc_sma(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Simple Moving Average"""
        period = params.get('period', 20)
        sma = df['close'].rolling(period).mean().iloc[-1]
        price = df['close'].iloc[-1]
        
        signal = 'BUY' if price > sma else 'SELL' if price < sma else 'NEUTRAL'
        confidence = abs(price - sma) / sma
        
        return IndicatorResult('SMA', sma, signal, confidence)
    
    def _calc_ema(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Exponential Moving Average"""
        period = params.get('period', 20)
        ema = df['close'].ewm(span=period).mean().iloc[-1]
        price = df['close'].iloc[-1]
        
        signal = 'BUY' if price > ema else 'SELL' if price < ema else 'NEUTRAL'
        confidence = abs(price - ema) / ema
        
        return IndicatorResult('EMA', ema, signal, confidence)
    
    def _calc_wma(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Weighted Moving Average"""
        period = params.get('period', 20)
        weights = np.arange(1, period + 1)
        wma = df['close'].tail(period).dot(weights) / weights.sum()
        price = df['close'].iloc[-1]
        
        signal = 'BUY' if price > wma else 'SELL' if price < wma else 'NEUTRAL'
        confidence = abs(price - wma) / wma
        
        return IndicatorResult('WMA', wma, signal, confidence)
    
    def _calc_macd(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """MACD"""
        fast = params.get('fast', 12)
        slow = params.get('slow', 26)
        signal_line = params.get('signal', 9)
        
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line_val = macd_line.ewm(span=signal_line).mean()
        histogram = macd_line - signal_line_val
        
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line_val.iloc[-1]
        
        signal = 'BUY' if current_macd > current_signal else 'SELL'
        confidence = abs(histogram.iloc[-1]) / abs(current_macd) if current_macd != 0 else 0
        
        return IndicatorResult('MACD', current_macd, signal, confidence)
    
    def _calc_adx(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Average Directional Index"""
        period = params.get('period', 14)
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([high - low, abs(high - close.shift()), abs(low - close.shift())], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean().iloc[-1]
        
        signal = 'BUY' if plus_di.iloc[-1] > minus_di.iloc[-1] else 'SELL'
        confidence = adx / 100.0
        
        return IndicatorResult('ADX', adx, signal, confidence)
    
    def _calc_atr(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Average True Range"""
        period = params.get('period', 14)
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        
        return IndicatorResult('ATR', atr, 'NEUTRAL', 0.5)
    
    def _calc_bollinger(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Bollinger Bands"""
        period = params.get('period', 20)
        std_dev = params.get('std_dev', 2)
        
        sma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        upper = sma + (std * std_dev)
        lower = sma - (std * std_dev)
        
        price = df['close'].iloc[-1]
        
        if price > upper.iloc[-1]:
            signal = 'SELL'  # Sobrecompra
        elif price < lower.iloc[-1]:
            signal = 'BUY'  # Sobreventa
        else:
            signal = 'NEUTRAL'
        
        confidence = (upper.iloc[-1] - lower.iloc[-1]) / sma.iloc[-1]
        
        return IndicatorResult('BOLLINGER', price, signal, confidence)
    
    def _calc_keltner(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Keltner Channels"""
        period = params.get('period', 20)
        atr_mult = params.get('atr_mult', 2)
        
        ema = df['close'].ewm(span=period).mean()
        atr = self._calc_atr(df, {'period': period}).value
        upper = ema + (atr * atr_mult)
        lower = ema - (atr * atr_mult)
        
        price = df['close'].iloc[-1]
        
        if price > upper.iloc[-1]:
            signal = 'BUY'
        elif price < lower.iloc[-1]:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        confidence = (upper.iloc[-1] - lower.iloc[-1]) / ema.iloc[-1]
        
        return IndicatorResult('KELTNER', price, signal, confidence)
    
    def _calc_rsi(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Relative Strength Index"""
        period = params.get('period', 14)
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs)).iloc[-1]
        
        if rsi < 30:
            signal = 'BUY'  # Sobreventa
        elif rsi > 70:
            signal = 'SELL'  # Sobrecompra
        else:
            signal = 'NEUTRAL'
        
        confidence = abs(50 - rsi) / 50.0
        
        return IndicatorResult('RSI', rsi, signal, confidence)
    
    def _calc_stochastic(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Stochastic Oscillator"""
        period = params.get('period', 14)
        smooth_k = params.get('smooth_k', 3)
        smooth_d = params.get('smooth_d', 3)
        
        low_min = df['low'].rolling(period).min()
        high_max = df['high'].rolling(period).max()
        k = 100 * ((df['close'] - low_min) / (high_max - low_min))
        k = k.rolling(smooth_k).mean()
        d = k.rolling(smooth_d).mean()
        
        current_k = k.iloc[-1]
        current_d = d.iloc[-1]
        
        if current_k < 20 and current_d < 20:
            signal = 'BUY'
        elif current_k > 80 and current_d > 80:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        return IndicatorResult('STOCHASTIC', current_k, signal, 0.5)
    
    def _calc_cci(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Commodity Channel Index"""
        period = params.get('period', 20)
        
        tp = (df['high'] + df['low'] + df['close']) / 3
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())))
        cci = (tp - sma_tp) / (0.015 * mad)
        
        current_cci = cci.iloc[-1]
        
        if current_ci < -100:
            signal = 'BUY'
        elif current_cci > 100:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        return IndicatorResult('CCI', current_cci, signal, 0.5)
    
    def _calc_momentum(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Momentum"""
        period = params.get('period', 10)
        
        momentum = df['close'].diff(period).iloc[-1]
        prev_momentum = df['close'].diff(period).iloc[-2]
        
        signal = 'BUY' if momentum > 0 else 'SELL' if momentum < 0 else 'NEUTRAL'
        confidence = abs(momentum) / df['close'].iloc[-1]
        
        return IndicatorResult('MOMENTUM', momentum, signal, confidence)
    
    def _calc_roc(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Rate of Change"""
        period = params.get('period', 10)
        
        roc = ((df['close'].iloc[-1] - df['close'].iloc[-period-1]) / 
               df['close'].iloc[-period-1]) * 100
        
        signal = 'BUY' if roc > 0 else 'SELL' if roc < 0 else 'NEUTRAL'
        confidence = min(abs(roc) / 10.0, 1.0)
        
        return IndicatorResult('ROC', roc, signal, confidence)
    
    def _calc_obv(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """On Balance Volume"""
        obv = (np.sign(df['close'].diff()) * df['volume']).cumsum()
        current_obv = obv.iloc[-1]
        
        signal = 'BUY' if obv.iloc[-1] > obv.iloc[-5] else 'SELL'
        confidence = 0.5
        
        return IndicatorResult('OBV', current_obv, signal, confidence)
    
    def _calc_volume_profile(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Volume Profile (nivel de volumen)"""
        period = params.get('period', 20)
        avg_volume = df['volume'].tail(period).mean()
        current_volume = df['volume'].iloc[-1]
        
        ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        if ratio > 1.5:
            signal = 'BUY'  # Alto volumen
        elif ratio < 0.5:
            signal = 'SELL'  # Bajo volumen
        else:
            signal = 'NEUTRAL'
        
        return IndicatorResult('VOLUME_PROFILE', ratio, signal, abs(ratio - 1))
    
    def _calc_mfi(self, df: pd.DataFrame, params: Dict) -> IndicatorResult:
        """Money Flow Index"""
        period = params.get('period', 14)
        
        tp = (df['high'] + df['low'] + df['close']) / 3
        raw_mf = tp * df['volume']
        
        pos_mf = raw_mf.where(tp > tp.shift(1), 0).rolling(period).sum()
        neg_mf = raw_mf.where(tp < tp.shift(1), 0).rolling(period).sum()
        
        mfi = 100 - (100 / (1 + pos_mf / neg_mf))
        current_mfi = mfi.iloc[-1]
        
        if current_mfi < 20:
            signal = 'BUY'
        elif current_mfi > 80:
            signal = 'SELL'
        else:
            signal = 'NEUTRAL'
        
        return IndicatorResult('MFI', current_mfi, signal, 0.5)


# Función de conveniencia
def create_indicator_engine() -> IndicatorEngine:
    """Factory para crear el motor de indicadores"""
    return IndicatorEngine()


if __name__ == "__main__":
    print("Testing Indicator Engine v2.0...")
    print("=" * 60)
    
    # Datos de prueba
    np.random.seed(42)
    prices = [100.0]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    df = pd.DataFrame({
        'open': prices,
        'high': [p * 1.02 for p in prices],
        'low': [p * 0.98 for p in prices],
        'close': prices,
        'volume': np.random.randint(1000, 10000, 101)
    })
    
    engine = IndicatorEngine()
    
    # Test indicadores
    print("\n📊 Indicadores calculados:")
    for name in ['rsi', 'macd', 'atr', 'bollinger', 'stochastic']:
        result = engine.calculate(df, name)
        if result:
            print(f"   {name}: {result.value:.4f} | Señal: {result.signal}")
    
    # Test todos
    all_indicators = engine.calculate_all(df, 'TEST')
    print(f"\n✅ Total indicadores: {len(all_indicators)}")
    
    # Test combinación
    combos = engine.combine_indicators(df, [
        {'type': 'AND', 'indicators': ['rsi', 'macd']},
        {'type': 'OR', 'indicators': ['sma', 'bollinger']}
    ])
    print(f"\n✅ Combinaciones: {len(combos)}")
    
    print("\n✅ Indicator Engine v2.0 funcionando correctamente")