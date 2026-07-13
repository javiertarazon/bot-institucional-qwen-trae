"""
Cline Brain Integration para CIP Lite v2.0
Motor de decisión inteligente que usa el agente como cerebro del trading
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import structlog
import json

from services.strategies.enhanced_strategies import (
    MeanReversionStrategy, 
    MomentumStrategy, 
    EnsembleStrategy,
    StrategySignal
)
from services.risk.dynamic_risk_manager import DynamicRiskManager, AdaptivePositionSizer

logger = structlog.get_logger()


@dataclass
class MarketAnalysis:
    """Análisis completo del mercado para Cline"""
    symbol: str
    price: float
    trend: str  # bullish, bearish, neutral
    volatility: float
    volume_profile: str  # high, normal, low
    sentiment_score: float  # -1 to 1
    support_levels: List[float]
    resistance_levels: List[float]
    timestamp: datetime


class ClineBrain:
    """
    Integración del agente Cline como cerebro del trading
    Analiza datos de mercado y genera decisiones inteligentes
    """
    
    def __init__(self, risk_manager: DynamicRiskManager = None):
        self.risk_manager = risk_manager or DynamicRiskManager()
        self.position_sizer = AdaptivePositionSizer()
        self.strategies = {
            'mean_reversion': MeanReversionStrategy(),
            'momentum': MomentumStrategy(),
        }
        self.ensemble = EnsembleStrategy(list(self.strategies.values()))
        self.analysis_history: List[MarketAnalysis] = []
        
    def analyze_market(self, df: pd.DataFrame, symbol: str, 
                       sentiment_score: float = 0.0) -> MarketAnalysis:
        """Analiza el mercado y prepara contexto para Cline"""
        
        if len(df) < 50:
            raise ValueError(f"Insuficientes datos para {symbol}: {len(df)} < 50")
        
        close = df['close']
        volume = df['volume']
        
        # Análisis de tendencia
        ma21 = close.rolling(21).mean()
        ma50 = close.rolling(50).mean()
        price_vs_ma21 = (close.iloc[-1] / ma21.iloc[-1]) - 1
        price_vs_ma50 = (close.iloc[-1] / ma50.iloc[-1]) - 1
        
        if price_vs_ma21 > 0.02 and price_vs_ma50 > 0.02:
            trend = 'bullish'
        elif price_vs_ma21 < -0.02 and price_vs_ma50 < -0.02:
            trend = 'bearish'
        else:
            trend = 'neutral'
        
        # Volatilidad
        volatility = close.pct_change().rolling(20).std().iloc[-1]
        
        # Perfil de volumen
        vol_ma20 = volume.rolling(20).mean()
        vol_ratio = volume.iloc[-1] / vol_ma20.iloc[-1]
        
        if vol_ratio > 1.5:
            volume_profile = 'high'
        elif vol_ratio < 0.7:
            volume_profile = 'low'
        else:
            volume_profile = 'normal'
        
        # Support/Resistance levels (simples)
        support = [close.min()]
        resistance = [close.max()]
        
        analysis = MarketAnalysis(
            symbol=symbol,
            price=close.iloc[-1],
            trend=trend,
            volatility=volatility,
            volume_profile=volume_profile,
            sentiment_score=sentiment_score,
            support_levels=support,
            resistance_levels=resistance,
            timestamp=datetime.now()
        )
        
        self.analysis_history.append(analysis)
        return analysis
    
    def generate_trading_decision(self, df: pd.DataFrame, symbol: str,
                                   sentiment_score: float = 0.0) -> StrategySignal:
        """
        Genera decisión de trading usando el ensemble + ajustes de Cline
        """
        # Analizar mercado
        analysis = self.analyze_market(df, symbol, sentiment_score)
        
        # Ajustar estrategias según régimen
        market_regime = self.position_sizer.detect_regime(df)
        
        logger.info(f"Generating decision for {symbol}", 
                   trend=analysis.trend,
                   volatility=f"{analysis.volatility:.2%}",
                   market_regime=market_regime)
        
        # Obtener señal del ensemble
        signal = self.ensemble(df, symbol)
        
        # Ajustaciones por Cline Brain
        if signal.signal in ('BUY', 'SELL'):
            # Ajustar stops/take_profit según volatilidad
            direction = "long" if signal.signal == "BUY" else "short"
            signal.stop_loss = self.risk_manager.calculate_dynamic_stop(
                signal.entry_price, df, direction
            )
            
            # Si tendencia opuesta al sentimiento, reducir confianza
            if (analysis.trend == 'bearish' and signal.signal == 'BUY') or \
               (analysis.trend == 'bullish' and signal.signal == 'SELL'):
                signal.confidence *= 0.7
                logger.info("Reducing confidence due to trend-sentinment conflict")
            
            # Si volumen bajo, reducir sizing
            if analysis.volume_profile == 'low':
                signal.confidence *= 0.8
        
        return signal
    
    def generate_trade_summary(self, signal: StrategySignal, analysis: MarketAnalysis,
                              df: pd.DataFrame) -> str:
        """Genera un resumen legible para el usuario"""
        
        summary = f"""
🧠 **Cline Brain - Decisión de Trading**
==========================================
Símbolo: {signal.symbol}
Señal: **{signal.signal}** (confianza: {signal.confidence:.1%})
Precio entrada: ${signal.entry_price:,.2f}

📊 **Análisis de Mercado**
- Tendencia: {analysis.trend.upper()}
- Volatilidad: {analysis.volatility:.2%}
- Volumen: {analysis.volume_profile.upper()}

🛡️ **Gestión de Riesgo**
- Stop Loss: ${signal.stop_loss:,.2f}
- Take Profit: ${signal.take_profit:,.2f}
- Ratio Riesgo/Beneficio: 1:{(signal.take_profit - signal.entry_price)/(signal.entry_price - signal.stop_loss):.1f}

💰 **Tamaño de Posición Sugerido**
- Basado en Kelly variable y volatilidad
- Max exposición diaria: 2% (VaR)
        """
        
        return summary.strip()
    
    def run_backtest_with_strategies(self, prices: List[float], symbol: str = "BTC") -> Dict:
        """
        Ejecuta backtest usando las nuevas estrategias
        """
        from services.backtesting.engine import BacktestEngine, BacktestConfig
        
        # Preparar datos
        dates = pd.date_range(end=datetime.now(), periods=len(prices), freq='D')
        df = pd.DataFrame({
            'Date': dates,
            'Open': prices,
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': np.random.randint(10000, 100000, len(prices))
        }).set_index('Date')
        
        # Estrategia del ensemble como función
        def ensemble_strategy(data):
            signal = self.ensemble(data.reset_index(), symbol)
            return signal.signal
        
        # Ejecutar backtest
        config = BacktestConfig()
        engine = BacktestEngine(config)
        results = engine.run(df, ensemble_strategy)
        
        return results


class ClineTradeExecutor:
    """
    Ejecutor que coordina Cline + Risk Manager + Execution Engine
    """
    
    def __init__(self):
        self.brain = ClineBrain()
        self.risk_mgr = DynamicRiskManager()
        
    def execute_analysis_cycle(self, market_data: pd.DataFrame, 
                                symbol: str, sentiment: float = 0.0) -> Dict:
        """
        Ejecuta un ciclo completo: analisis -> decision -> risk check -> execute
        """
        # 1. Análisis
        analysis = self.brain.analyze_market(market_data, symbol, sentiment)
        
        # 2. Decisión
        signal = self.brain.generate_trading_decision(market_data, symbol, sentiment)
        
        # 3. Verificación de riesgo
        risk_check = self._check_risk_limits(signal, analysis)
        
        # 4. Resumen
        summary = self.brain.generate_trade_summary(signal, analysis, market_data)
        
        return {
            'analysis': analysis.__dict__,
            'signal': signal.__dict__,
            'risk_approved': risk_check['approved'],
            'risk_issues': risk_check['issues'],
            'summary': summary
        }
    
    def _check_risk_limits(self, signal: StrategySignal, 
                            analysis: MarketAnalysis) -> Dict:
        """Verifica límites de riesgo antes de ejecutar"""
        issues = []
        
        # Check drawdown
        if self.risk_mgr.current_capital < self.risk_mgr.peak_value * 0.9:
            issues.append("Drawdown > 10%")
            return {'approved': False, 'issues': issues}
        
        # Check daily VaR
        var = self.risk_mgr.value_at_risk()
        if var > self.risk_mgr.current_capital * 0.02:
            issues.append(f"VaR diario excedido: {var/self.risk_mgr.current_capital:.1%}")
        
        # Check position size
        if analysis.volatility > 0.1:  # 10% volatilidad extrema
            issues.append("Volatilidad extrema - reducir posición")
        
        return {
            'approved': len(issues) == 0,
            'issues': issues
        }


# Función de conveniencia
def create_cline_brain() -> ClineBrain:
    """Factory para crear una instancia del cerebro Cline"""
    return ClineBrain()


if __name__ == "__main__":
    print("🧠 Cline Brain Integration Test")
    print("=" * 60)
    
    # Crear datos de prueba
    np.random.seed(42)
    prices = [50000]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    df = pd.DataFrame({
        'close': prices,
        'high': [p * 1.03 for p in prices],
        'low': [p * 0.97 for p in prices],
        'volume': np.random.randint(10000, 100000, 101)
    })
    
    # Test del cerebro
    brain = ClineBrain()
    analysis = brain.analyze_market(df, "BTC", sentiment_score=0.3)
    
    print(f"\n📊 Análisis de Mercado:")
    print(f"   Precio: ${analysis.price:,.2f}")
    print(f"   Tendencia: {analysis.trend}")
    print(f"   Volatilidad: {analysis.volatility:.2%}")
    
    signal = brain.generate_trading_decision(df, "BTC", 0.3)
    print(f"\n🎯 Señal Generada: {signal.signal}")
    print(f"   Confianza: {signal.confidence:.1%}")
    
    print(f"\n✅ Cline Brain integration funcionando!")