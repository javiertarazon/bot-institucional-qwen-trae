"""
Whale Tracker - Detección de actividad institucional
Detecta acumulación/distribución mediante trades grandes
"""

import polars as pl
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()


class WhaleTracker:
    """
    Detecta actividad institucional en exchanges centralizados.
    No requiere nodos RPC - usa trades públicos como proxy.
    """
    
    def __init__(self, lookback_trades: int = 500):
        self.lookback = lookback_trades
        self.whale_threshold_percentile = 95.0
    
    def analyze_order_flow(self, recent_trades: pl.DataFrame) -> dict:
        """
        Analiza el flujo de órdenes para detectar actividad de ballenas.
        
        Args:
            recent_trades: DataFrame con ['price', 'volume', 'side', 'timestamp']
        
        Returns:
            dict con whale_activity, absorption_detected, whale_delta_usd
        """
        if recent_trades.is_empty() or len(recent_trades) < 50:
            return {"whale_activity": "NEUTRAL", "absorption_detected": False}
        
        try:
            # 1. Identificar trades de ballena (Top 5% por tamaño)
            threshold = recent_trades.select(
                pl.col('volume').quantile(self.whale_threshold_percentile / 100)
            ).item()
            
            whales = recent_trades.filter(pl.col('volume') >= threshold)
            
            if whales.is_empty():
                return {"whale_activity": "NEUTRAL", "absorption_detected": False}
            
            # 2. Calcular delta de ballenas
            whale_buys = whales.filter(pl.col('side') == 'buy')['volume'].sum() or 0
            whale_sells = whales.filter(pl.col('side') == 'sell')['volume'].sum() or 0
            whale_delta = whale_buys - whale_sells
            
            # 3. Detectar absorción (precio vs ballenas)
            price_change = float(
                recent_trades['price'][-1] - recent_trades['price'][0]
            )
            
            absorption = False
            if price_change < 0 and whale_delta > 0 and whale_delta > whale_sells * 1.5:
                absorption = True
                activity = "BULLISH_ABSORPTION"
            elif price_change > 0 and whale_delta < 0 and abs(whale_delta) > whale_buys * 1.5:
                absorption = True
                activity = "BEARISH_ABSORPTION"
            else:
                activity = "AGGRESSIVE_TREND" if abs(whale_delta) > (whale_buys + whale_sells) * 0.3 else "NEUTRAL"
            
            return {
                "whale_activity": activity,
                "absorption_detected": absorption,
                "whale_delta_usd": float(whale_delta),
                "trade_count": len(whales)
            }
            
        except Exception as e:
            logger.debug(f"Error en whale tracker: {e}")
            return {"whale_activity": "NEUTRAL", "absorption_detected": False}


# Singleton
_whale_tracker_instance = None

def get_whale_tracker() -> WhaleTracker:
    """Factory singleton para Whale Tracker"""
    global _whale_tracker_instance
    if _whale_tracker_instance is None:
        _whale_tracker_instance = WhaleTracker()
    return _whale_tracker_instance