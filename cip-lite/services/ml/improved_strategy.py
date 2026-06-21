"""
Estrategia mejorada basada en la línea base
"""
import numpy as np
import pandas as pd
from typing import Optional
import structlog

logger = structlog.get_logger()

class ImprovedTrendStrategy:
    """Estrategia mejorada con gestión de riesgo y mejores indicadores"""
    
    def __init__(self):
        self.ma_short_window = 7
        self.ma_long_window = 21
        self.rsi_window = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        self.stop_loss_pct = 0.02
        self.take_profit_pct = 0.05
        
        self.entry_price: Optional[float] = None
        self.last_high: Optional[float] = None
        self.current_position: Optional[str] = None
        logger.info("ImprovedTrendStrategy inicializada")
    
    def calculate_rsi(self, series: pd.Series, window: int = 14) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def __call__(self, df_hist: pd.DataFrame) -> str:
        df = df_hist.copy()
        if len(df) < 30:
            return 'HOLD'
        
        # Calculate indicators
        df['ma7'] = df['Close'].rolling(window=self.ma_short_window).mean()
        df['ma21'] = df['Close'].rolling(window=self.ma_long_window).mean()
        df['rsi'] = self.calculate_rsi(df['Close'], self.rsi_window)
        
        current_price = df['Close'].iloc[-1]
        ma7 = df['ma7'].iloc[-1]
        ma21 = df['ma21'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        prev_ma7 = df['ma7'].iloc[-2]
        prev_ma21 = df['ma21'].iloc[-2]
        
        if self.current_position == 'LONG':
            # Update last high
            if current_price > self.last_high:
                self.last_high = current_price
            
            # Check stop loss or take profit
            if current_price < self.entry_price * (1 - self.stop_loss_pct):
                logger.info("Stop loss activado", entry=self.entry_price, current=current_price)
                self.current_position = None
                return 'SELL'
            
            if current_price > self.entry_price * (1 + self.take_profit_pct):
                logger.info("Take profit activado", entry=self.entry_price, current=current_price)
                self.current_position = None
                return 'SELL'
            
            # Check bearish crossover
            if ma7 < ma21 and prev_ma7 > prev_ma21:
                logger.info("Cruce bajista, cerrando posición")
                self.current_position = None
                return 'SELL'
        
        elif self.current_position is None:
            # Bullish crossover + RSI not overbought
            if ma7 > ma21 and prev_ma7 < prev_ma21 and rsi < 65:
                self.current_position = 'LONG'
                self.entry_price = current_price
                self.last_high = current_price
                logger.info("Señal de compra", price=current_price)
                return 'BUY'
        
        return 'HOLD'
