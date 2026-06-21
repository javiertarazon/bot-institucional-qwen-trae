"""
Estrategia Optimizada 2.0 - Enfocada en Mejora Sustancial
Aumenta la exposición en tendencias claras y reduce drawdown
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class OptimizedStrategyV2:
    """Estrategia para maximizar rendimiento reduciendo drawdown"""
    def __init__(self):
        self.ma_short_win = 5
        self.ma_long_win = 30
        self.risk_pct = 0.02
        self.stop_loss_pct = 0.015
        self.take_profit_pct = 0.035
        self.entry_price = None
        self.position = None  # 'LONG' o None
        self.last_high = None
        logger.info("OptimizedStrategyV2 inicializada")

    def __call__(self, df_hist: pd.DataFrame) -> str:
        df = df_hist.copy()
        df['ma_short'] = df['Close'].rolling(self.ma_short_win).mean()
        df['ma_long'] = df['Close'].rolling(self.ma_long_win).mean()

        if len(df) < self.ma_long_win:
            return 'HOLD'

        current_price = df['Close'].iloc[-1]
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        prev_ma_short = df['ma_short'].iloc[-2]
        prev_ma_long = df['ma_long'].iloc[-2]

        # 1. Verificar cierre de posición
        if self.position == 'LONG':
            if current_price > self.last_high:
                self.last_high = current_price
            # Stop loss hard
            if current_price < self.entry_price * (1 - self.stop_loss_pct):
                logger.info("Stop loss activado", price=current_price)
                self.position = None
                return 'SELL'
            # Take profit
            if current_price > self.entry_price * (1 + self.take_profit_pct):
                logger.info("Take profit activado", price=current_price)
                self.position = None
                return 'SELL'

        # 2. Verificar aperturas: cruce + tendencia clara (pendiente positiva de la ma larga)
        long_ma_pct = (ma_long - prev_ma_long) / prev_ma_long if prev_ma_long !=0 else 0
        is_uptrend = long_ma_pct > 0.0005

        # Cruce bullish + tendencia alcista
        if (self.position is None and
            ma_short > ma_long and
            prev_ma_short < prev_ma_long and
            is_uptrend):
            self.position = 'LONG'
            self.entry_price = current_price
            self.last_high = current_price
            logger.info("Compra: cruzamiento + tendencia alcista", price=current_price)
            return 'BUY'

        # Cruce bearish para cerrar posición
        if (self.position == 'LONG' and
            ma_short < ma_long and
            prev_ma_short > prev_ma_long):
            logger.info("Venta: cruzamiento bajista", price=current_price)
            self.position = None
            return 'SELL'

        return 'HOLD'
