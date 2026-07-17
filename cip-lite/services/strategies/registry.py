"""
Registry central de estrategias - CIP Lite v2.0
Única fuente de estrategias para backtest, paper trading y live trading.
Cualquier estrategia (Simple, ONNX, Enhanced) se registra aquí y es
seleccionable por nombre desde run_full_backtest.py / main.py.
"""
import pandas as pd
from services.strategies.base_strategy import BaseStrategy, StrategyRegistry
from services.strategies.enhanced_strategies import (
    MeanReversionStrategy, MomentumStrategy, BreakoutStrategy,
    MarketMakingStrategy, SentimentContrarianStrategy, EnsembleStrategyV2,
)
from services.strategies.onnx_regime_strategy import ONNXRegimeStrategy

# Adaptador: convierte una BaseStrategy (devuelve StrategySignal) al callable
# str -> 'BUY'/'SELL'/'HOLD' que espera BacktestEngine.
class StrategyAdapter:
    """Envuelve una BaseStrategy para ser usada como estrategia del motor de backtest.
    Normaliza el DataFrame a columnas minúsculas (formato interno de las
    estrategias en enhanced_strategies / onnx_regime_strategy)."""

    _MAP = {'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy

    @staticmethod
    def _to_lower(df: pd.DataFrame) -> pd.DataFrame:
        rename = {c: StrategyAdapter._MAP[c] for c in df.columns if c in StrategyAdapter._MAP}
        return df.rename(columns=rename) if rename else df

    def __call__(self, data, symbol: str = "BTC"):
        df = self._to_lower(data)
        sig = self.strategy(df, symbol)
        if sig is None:
            return "HOLD"
        return sig.signal


def build_registry() -> StrategyRegistry:
    """Construye y registra todas las estrategias disponibles."""
    reg = StrategyRegistry()
    reg.register(MeanReversionStrategy(), category="trend",
                 description="Mean reversion con RSI + Bollinger")
    reg.register(MomentumStrategy(), category="trend",
                 description="Momentum multi-timeframe EMA+MACD")
    reg.register(BreakoutStrategy(), category="breakout",
                 description="Breakout con confirmación de volumen")
    reg.register(MarketMakingStrategy(), category="market_making",
                 description="Market making adaptativo")
    reg.register(SentimentContrarianStrategy(), category="sentiment",
                 description="Contrarian basado en sentimiento extremo")
    reg.register(ONNXRegimeStrategy(), category="ml",
                 description="Régimen de mercado con modelo ONNX")
    # Ensemble de las estrategias clásicas (requiere 2+ votos)
    ensemble = EnsembleStrategyV2(
        [MeanReversionStrategy(), MomentumStrategy(),
         BreakoutStrategy(), SentimentContrarianStrategy()],
        min_votes=2,
    )
    reg.register(ensemble, category="ensemble",
                 description="Ensemble de estrategias clásicas (2+ votos)")
    return reg


# Instancia global del registry
REGISTRY = build_registry()


def get_strategy_callable(name: str) -> callable:
    """Devuelve un callable compatible con BacktestEngine para el nombre dado."""
    strat = REGISTRY.get(name)
    if strat is None:
        raise KeyError(f"Estrategia '{name}' no registrada. "
                       f"Disponibles: {[s['name'] for s in REGISTRY.list_strategies()]}")
    return StrategyAdapter(strat)