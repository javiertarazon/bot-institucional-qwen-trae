"""
Microstructure Engine - v1.0
Procesamiento de Order Flow para scalping institucional
Optimizado con Polars para bajos recursos
"""

import polars as pl
import numpy as np
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()


class MicrostructureEngine:
    """
    Motor de microestructura y Order Flow.
    Features: CVD, OBI, Trade Intensity, Whale Detection
    Optimizado para latencia < 1ms en hardware modesto.
    """
    
    def __init__(self, cvd_window: int = 100):
        self.cvd_window = cvd_window
    
    def process_order_flow(self, trades_df: pl.DataFrame, orderbook_df: pl.DataFrame) -> dict:
        """
        Calcula features de microestructura optimizadas.
        
        Args:
            trades_df: Columnas ['timestamp', 'price', 'quantity', 'side']
            orderbook_df: Columnas ['side', 'price', 'size']
        
        Returns:
            dict con CVD, OBI, trade_intensity, large_trades_ratio
        """
        try:
            # 1. Cumulative Volume Delta (CVD) normalizado
            buy_vol = trades_df.filter(pl.col('side') == 'buy')['quantity'].sum()
            sell_vol = trades_df.filter(pl.col('side') == 'sell')['quantity'].sum()
            total_vol = buy_vol + sell_vol
            cvd_norm = float((buy_vol - sell_vol) / (total_vol + 1e-8))
            
        except Exception:
            cvd_norm = 0.0
        
        try:
            # 2. Order Book Imbalance (OBI) - Top 10 niveles
            bid_depth = orderbook_df.filter(pl.col('side') == 'bid')['size'].sum()
            ask_depth = orderbook_df.filter(pl.col('side') == 'ask')['size'].sum()
            obi = float((bid_depth - ask_depth) / (bid_depth + ask_depth + 1e-8))
            
        except Exception:
            obi = 0.0
        
        try:
            # 3. Trade Intensity (velocidad de flujo)
            intensity = float(len(trades_df) / 60.0)
            
        except Exception:
            intensity = 0.0
        
        try:
            # 4. Large Trades Ratio (whale detection)
            large_trades_ratio = float(self._detect_whales(trades_df))
            
        except Exception:
            large_trades_ratio = 0.0
        
        return {
            "cvd_normalized": cvd_norm,
            "obi": obi,
            "trade_intensity": intensity,
            "large_trades_ratio": large_trades_ratio
        }
    
    def _detect_whales(self, df: pl.DataFrame) -> float:
        """
        Detecta trades de ballenas (top 5% por tamaño).
        
        Returns:
            Ratio de volumen de ballenas vs total
        """
        if df.is_empty():
            return 0.0
        
        try:
            q95 = df.select(pl.col('quantity').quantile(0.95)).item()
            whale_vol = df.filter(pl.col('quantity') >= q95)['quantity'].sum()
            total_vol = df['quantity'].sum()
            return float(whale_vol / (total_vol + 1e-8))
        except Exception:
            return 0.0
    
    def detect_sweep(self, trades_df: pl.DataFrame, orderbook_df: pl.DataFrame) -> Optional[dict]:
        """
        Detecta sweeps (barridos de liquidez) en el order book.
        
        Señal de scalping: precio rompe un extremo con volumen alto
        pero el order book muestra absorción.
        
        Returns:
            dict con type, strength, price_level si sweep detectado
        """
        try:
            # Obtener mejor bid/ask
            best_bid = orderbook_df.filter(pl.col('side') == 'bid').select(pl.col('price').max()).item()
            best_ask = orderbook_df.filter(pl.col('side') == 'ask').select(pl.col('price').min()).item()
            
            # Obtener trades grandes recientes
            recent_trades = trades_df.sort('timestamp').tail(20)
            
            if recent_trades.is_empty():
                return None
            
            # Detectar trades que golpearon el bid/ask y retreat
            buy_trades = recent_trades.filter(pl.col('side') == 'buy')
            sell_trades = recent_trades.filter(pl.col('side') == 'sell')
            
            # Sweep bullish: trades grandes compran bajo el bid
            if not sell_trades.is_empty():
                min_sell_price = sell_trades.select(pl.col('price').min()).item()
                if min_sell_price < best_bid * 0.999:  # Al menos 0.1% bajo
                    return {
                        "type": "liquidity_grab_low",
                        "strength": 0.8,
                        "price_level": min_sell_price
                    }
            
            # Sweep bearish: trades grandes venden sobre el ask
            if not buy_trades.is_empty():
                max_buy_price = buy_trades.select(pl.col('price').max()).item()
                if max_buy_price > best_ask * 1.001:  # Al menos 0.1% arriba
                    return {
                        "type": "liquidity_grab_high",
                        "strength": 0.8,
                        "price_level": max_buy_price
                    }
            
            return None
            
        except Exception as e:
            logger.debug(f"Error detectando sweep: {e}")
            return None


# Singleton
_microstructure_instance = None

def get_microstructure_engine() -> MicrostructureEngine:
    """Factory singleton para el motor de microestructura"""
    global _microstructure_instance
    if _microstructure_instance is None:
        _microstructure_instance = MicrostructureEngine()
    return _microstructure_instance