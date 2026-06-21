"""
Estrategia Mejorada - Gestión de Riesgo Dinámica
Incluye trailing stop, take profit y mejora en la tasa de aciertos
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

class AdvancedTradingStrategy:
    """Estrategia avanzada con gestión de riesgo"""
    def __init__(self):
        self.ma_short_window = 7
        self.ma_long_window = 21
        self.trailing_stop_pct = 0.02  # 2%
        self.take_profit_pct = 0.05  # 5%
        self.entry_price = None
        self.last_high = None
        self.current_position = None  # 'LONG', 'SHORT', None
        logger.info("AdvancedTradingStrategy inicializada")

    def __call__(self, df_hist: pd.DataFrame) -> str:
        df = df_hist.copy()
        # Calcular medias móviles
        df['ma_short'] = df['Close'].rolling(self.ma_short_window).mean()
        df['ma_long'] = df['Close'].rolling(self.ma_long_window).mean()

        # Estado actual
        current_price = df['Close'].iloc[-1]
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        prev_ma_short = df['ma_short'].iloc[-2]
        prev_ma_long = df['ma_long'].iloc[-2]

        # 1. Revisar cierre de posición por trailing stop o take profit
        if self.current_position == 'LONG':
            if current_price > self.last_high:
                self.last_high = current_price
            # Trailing stop
            if current_price < self.last_high * (1 - self.trailing_stop_pct):
                logger.info("Trailing stop activado", current_price=current_price, stop=self.last_high*(1-self.trailing_stop_pct))
                self.current_position = None
                return 'SELL'
            # Take profit
            if current_price > self.entry_price * (1 + self.take_profit_pct):
                logger.info("Take profit activado", current_price=current_price)
                self.current_position = None
                return 'SELL'

        # 2. Revisar apertura de posición (cruces de medias móviles)
        # Cruce bullish: ma_short > ma_long y antes era ma_short < ma_long
        if (self.current_position is None and
            ma_short > ma_long and
            prev_ma_short < prev_ma_long):
            self.current_position = 'LONG'
            self.entry_price = current_price
            self.last_high = current_price
            logger.info("Señal de compra generada", price=current_price)
            return 'BUY'

        # 3. Cruce bearish (simplificado)
        if (self.current_position == 'LONG' and
            ma_short < ma_long and
            prev_ma_short > prev_ma_long):
            logger.info("Señal de venta por cruce bearish", price=current_price)
            self.current_position = None
            return 'SELL'

        return 'HOLD'
