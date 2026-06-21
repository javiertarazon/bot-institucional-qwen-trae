"""
Estrategia Mejorada con Gestión de Riesgo Dinámica y Mejoras Estructurales
Incluye: filtros de señal, protección contra drawdown, SL/TP dinámicos
"""
import numpy as np
import pandas as pd
from typing import Dict, Optional, Any
import structlog

logger = structlog.get_logger()


class EnhancedTradingStrategy:
    def __init__(
        self,
        ma_short_win=7,
        ma_long_win=30,
        rsi_period=14,
        rsi_overbought=70,
        rsi_oversold=30,
        max_drawdown_limit=-0.08,  # Detener trading si drawdown >8%
        base_position_pct=0.08,
        stop_loss_pct=0.015,
        take_profit_pct=0.04,
        trailing_stop_pct=0.02
    ):
        self.ma_short_win = ma_short_win
        self.ma_long_win = ma_long_win
        self.rsi_period = rsi_period
        self.rsi_overbought = rsi_overbought
        self.rsi_oversold = rsi_oversold
        self.max_drawdown_limit = max_drawdown_limit
        self.base_position_pct = base_position_pct
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct

        # Estado interno
        self.entry_price: Optional[float] = None
        self.position: Optional[str] = None  # 'LONG', None
        self.highest_price_in_position: Optional[float] = None
        self.peak_capital: float = 100000.0
        self.current_capital: float = 100000.0
        self.trading_paused: bool = False
        self.trade_history: list = []
        logger.info("Estrategia Mejorada inicializada")

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Medias móviles
        df['ma_short'] = df['Close'].rolling(self.ma_short_win).mean()
        df['ma_long'] = df['Close'].rolling(self.ma_long_win).mean()
        df['ma_50'] = df['Close'].rolling(50).mean()
        df['ma_200'] = df['Close'].rolling(200).mean()

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))

        # Volatilidad (ATR proxy)
        df['returns'] = df['Close'].pct_change()
        df['volatility'] = df['returns'].rolling(20).std() * np.sqrt(365)

        return df

    def check_drawdown_protection(self) -> bool:
        current_drawdown = (self.current_capital - self.peak_capital) / self.peak_capital
        if current_drawdown <= self.max_drawdown_limit:
            if not self.trading_paused:
                logger.warning("⚠️ Protección contra drawdown activada: deteniendo operaciones")
                self.trading_paused = True
            return False  # No operar
        if self.trading_paused and current_drawdown > self.max_drawdown_limit * 0.5:
            logger.info("Reanudando operaciones: drawdown mejorado")
            self.trading_paused = False
        return True

    def calculate_position_size(self, volatility: float) -> float:
        # Ajustar tamaño según volatilidad (más volatilidad = tamaño menor)
        vol_multiplier = max(0.5, min(1.5, 0.3 / volatility if volatility > 0 else 1.0))
        return self.base_position_pct * vol_multiplier

    def __call__(self, df_hist: pd.DataFrame) -> str:
        # Actualizar capital peak
        if not self.trade_history:
            self.current_capital = 100000.0
        self.peak_capital = max(self.peak_capital, self.current_capital)

        # Comprobar protección contra drawdown
        if not self.check_drawdown_protection():
            return 'HOLD'

        # Calcular indicadores
        df = self.calculate_indicators(df_hist)
        if len(df) < 200:
            return 'HOLD'

        current_price = df['Close'].iloc[-1]
        ma_short = df['ma_short'].iloc[-1]
        ma_long = df['ma_long'].iloc[-1]
        ma_50 = df['ma_50'].iloc[-1]
        ma_200 = df['ma_200'].iloc[-1]
        rsi = df['rsi'].iloc[-1]
        volatility = df['volatility'].iloc[-1]
        prev_ma_short = df['ma_short'].iloc[-2]
        prev_ma_long = df['ma_long'].iloc[-2]

        # Señal básica de cruce + filtros
        long_condition = (
            ma_short > ma_long and
            prev_ma_short < prev_ma_long and
            (current_price > ma_50 or ma_50 > ma_200) and  # Tendencia alcista de mediano/long plazo
            rsi > 25 and rsi < 75  # Rango RSI más amplio
        )

        exit_condition = (
            ma_short < ma_long and prev_ma_short > prev_ma_long or
            rsi > self.rsi_overbought
        )

        # Lógica de operación
        if self.position == 'LONG':
            # Actualizar máximo para trailing stop
            if self.highest_price_in_position is None or current_price > self.highest_price_in_position:
                self.highest_price_in_position = current_price

            trailing_stop_price = self.highest_price_in_position * (1 - self.trailing_stop_pct)
            sl_price = self.entry_price * (1 - self.stop_loss_pct)
            tp_price = self.entry_price * (1 + self.take_profit_pct)

            # Salida
            if current_price <= trailing_stop_price or current_price <= sl_price or current_price >= tp_price or exit_condition:
                self.position = None
                self.highest_price_in_position = None
                return 'SELL'
            else:
                return 'HOLD'
        elif self.position is None and long_condition:
            self.position = 'LONG'
            self.entry_price = current_price
            self.highest_price_in_position = current_price
            logger.info("Señal de COMPRA activada con filtros")
            return 'BUY'
        else:
            return 'HOLD'

    def update_trade(self, trade_result: Dict[str, Any]):
        """Actualizar estado interno después de una operación"""
        self.trade_history.append(trade_result)
        if 'pnl' in trade_result:
            self.current_capital += trade_result['pnl']
