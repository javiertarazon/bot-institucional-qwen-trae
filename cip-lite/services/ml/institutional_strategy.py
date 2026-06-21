"""
Estrategia Institucional - Optimizada para Alto Rendimiento
Incluye: RSI, MACD, Medias Móviles, Gestión de Riesgo Dinámica, Sizing de Posiciones
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class InstitutionalTradingStrategy:
    """Estrategia de trading institucional optimizada con múltiples indicadores y gestión de riesgo"""
    
    def __init__(self, initial_capital: float = 100000.0):
        # Parámetros de estrategia (optimizados de Opt1)
        self.ma_short_window = 10
        self.ma_medium_window = 30
        self.ma_long_window = 60
        
        # Parámetros RSI
        self.rsi_window = 14
        self.rsi_overbought = 75
        self.rsi_oversold = 25
        
        # Parámetros MACD
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
        # Gestión de riesgo (optimizada de Opt1)
        self.stop_loss_pct = 0.025  # 2.5% stop loss
        self.take_profit_pct = 0.07  # 7% take profit (2.8:1 risk-reward)
        self.trailing_stop_pct = 0.025  # 2.5% trailing stop dinámico
        self.max_position_pct = 0.1  # 10% máximo por posición
        self.max_daily_loss_pct = 0.03  # 3% máximo pérdida diaria
        
        # Estado
        self.entry_price: Optional[float] = None
        self.entry_date: Optional[datetime] = None
        self.last_high: Optional[float] = None
        self.current_position: Optional[str] = None  # 'LONG', None
        self.daily_pnl = 0.0
        self.initial_capital = initial_capital
        
        logger.info("InstitutionalTradingStrategy inicializada")
    
    def calculate_rsi(self, series: pd.Series, window: int = 14) -> pd.Series:
        """Calcula el RSI (Relative Strength Index)"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, series: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calcula MACD, línea de señal e histograma"""
        ema_fast = series.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = series.ewm(span=self.macd_slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.macd_signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram
    
    def __call__(self, df_hist: pd.DataFrame) -> str:
        """Ejecuta la estrategia y retorna 'BUY', 'SELL' o 'HOLD'"""
        df = df_hist.copy()
        
        # Verificar datos suficientes
        min_required = max(self.ma_long_window, self.macd_slow) + 10
        if len(df) < min_required:
            return 'HOLD'
        
        # Calcular indicadores
        df['ma_short'] = df['Close'].rolling(window=self.ma_short_window).mean()
        df['ma_medium'] = df['Close'].rolling(window=self.ma_medium_window).mean()
        df['ma_long'] = df['Close'].rolling(window=self.ma_long_window).mean()
        df['rsi'] = self.calculate_rsi(df['Close'], self.rsi_window)
        df['macd'], df['macd_signal'], df['macd_hist'] = self.calculate_macd(df['Close'])
        
        # Valores actuales
        current_price = df['Close'].iloc[-1]
        current_rsi = df['rsi'].iloc[-1]
        current_ma_short = df['ma_short'].iloc[-1]
        current_ma_medium = df['ma_medium'].iloc[-1]
        current_ma_long = df['ma_long'].iloc[-1]
        current_macd = df['macd'].iloc[-1]
        current_macd_signal = df['macd_signal'].iloc[-1]
        current_macd_hist = df['macd_hist'].iloc[-1]
        
        # Valores anteriores para cruces
        prev_ma_short = df['ma_short'].iloc[-2]
        prev_ma_medium = df['ma_medium'].iloc[-2]
        prev_rsi = df['rsi'].iloc[-2]
        prev_macd = df['macd'].iloc[-2]
        prev_macd_signal = df['macd_signal'].iloc[-2]
        prev_macd_hist = df['macd_hist'].iloc[-2]
        
        # ========== LÓGICA DE CIERRE DE POSICIÓN ==========
        if self.current_position == 'LONG':
            # Actualizar último máximo para trailing stop
            if current_price > self.last_high:
                self.last_high = current_price
            
            # 1. Trailing stop dinámico (optimizado de Opt1)
            trailing_stop_price = self.last_high * (1 - self.trailing_stop_pct)
            if current_price <= trailing_stop_price:
                logger.info("Trailing stop activado", last_high=self.last_high,
                           current_price=current_price, stop_price=trailing_stop_price)
                self.current_position = None
                return 'SELL'
            
            # 2. Stop loss fijo
            if current_price < self.entry_price * (1 - self.stop_loss_pct):
                logger.info("Stop loss activado", entry_price=self.entry_price, 
                           current_price=current_price)
                self.current_position = None
                return 'SELL'
            
            # 3. Take profit
            if current_price > self.entry_price * (1 + self.take_profit_pct):
                logger.info("Take profit activado", entry_price=self.entry_price,
                           current_price=current_price)
                self.current_position = None
                return 'SELL'
            
            # 4. Señales de salida técnica
            exit_signals = 0
            
            # Cruce bajista de medias
            if current_ma_short < current_ma_medium and prev_ma_short > prev_ma_medium:
                exit_signals += 1
                logger.info("Señal de salida: cruce bajista medias")
            
            # RSI en sobrecompra
            if current_rsi > self.rsi_overbought:
                exit_signals += 1
                logger.info("Señal de salida: RSI sobrecompra", rsi=current_rsi)
            
            # MACD histograma negativo
            if current_macd_hist < 0 and prev_macd_hist > 0:
                exit_signals += 1
                logger.info("Señal de salida: MACD histograma negativo")
            
            if exit_signals >= 2:
                logger.info("Señal de venta por múltiples indicadores", exit_signals=exit_signals)
                self.current_position = None
                return 'SELL'
        
        # ========== LÓGICA DE APERTURA DE POSICIÓN ==========
        elif self.current_position is None:
            buy_signals = 0
            
            # 1. Tendencia alcista (MA corto > MA mediano > MA largo)
            if current_ma_short > current_ma_medium > current_ma_long:
                buy_signals += 2
                logger.debug("Señal de compra: tendencia alcista (3 medias)")
            
            # 2. RSI oversold y subiendo
            if prev_rsi < self.rsi_oversold and current_rsi > prev_rsi:
                buy_signals += 1
                logger.debug("Señal de compra: RSI oversold recuperándose", rsi=current_rsi)
            
            # 3. MACD bullish crossover
            if current_macd > current_macd_signal and prev_macd <= prev_macd_signal:
                buy_signals += 2
                logger.debug("Señal de compra: MACD bullish crossover")
            
            # 4. MACD histograma positivo y creciendo
            if current_macd_hist > 0 and current_macd_hist > prev_macd_hist:
                buy_signals += 1
                logger.debug("Señal de compra: MACD histograma creciente")
            
            # 5. Precio por encima de MA largo
            if current_price > current_ma_long:
                buy_signals += 1
                logger.debug("Señal de compra: precio por encima de MA largo")
            
            # Abrir posición si hay suficientes señales (umbral reducido de 5 a 4, Opt1)
            if buy_signals >= 4:
                self.current_position = 'LONG'
                self.entry_price = current_price
                self.last_high = current_price
                self.entry_date = df.index[-1]
                logger.info("Señal de compra activada", buy_signals=buy_signals,
                           entry_price=current_price)
                return 'BUY'
        
        return 'HOLD'
