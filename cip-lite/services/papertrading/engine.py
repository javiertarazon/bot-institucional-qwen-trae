#!/usr/bin/env python3
"""
📋 Paper Trading Engine - CIP v2.0
Simula operaciones en vivo como si fueran reales:
- Conexión CCXT solo-lectura (sin API keys)
- Estrategia ONNX para clasificación de régimen
- Contabilidad completa: P&L, equity curve, comisiones
- Dashboard en consola con estado actualizado
- Historial en SQLite para análisis posterior
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import json
import pickle
import sqlite3
import time
import structlog
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque
import warnings
warnings.filterwarnings("ignore")

logger = structlog.get_logger()

# ==================== CONFIGURACIÓN ====================
BASE_DIR = Path(__file__).parent.parent.parent
MODEL_DIR = BASE_DIR / "models"
DATA_DIR = BASE_DIR / "data" / "historical"
REPORTS_DIR = BASE_DIR / "reports"
DB_PATH = BASE_DIR / "data" / "papertrading.db"

# Constantes
INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001  # 0.1%
SLIPPAGE_PCT = 0.0005    # 0.05%
MAX_POSITION_PCT = 0.1   # 10% por posición
RISK_PER_TRADE = 0.02    # 2% riesgo por operación


@dataclass
class PaperTrade:
    """Registro de una operación de paper trading"""
    timestamp: datetime
    symbol: str
    side: str  # BUY or SELL
    price: float
    quantity: float
    cost: float
    commission: float
    pnl: float = 0.0
    pnl_pct: float = 0.0
    balance_after: float = 0.0
    regime: str = "LATERAL"
    confidence: float = 0.5
    strategy: str = ""
    exit_reason: str = ""


@dataclass
class PaperPosition:
    """Posición abierta en paper trading"""
    symbol: str
    side: str  # BUY (long) or SELL (short)
    entry_price: float
    quantity: float
    entry_cost: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    trailing_sl: float
    regime: str
    confidence: float


class PaperTradingEngine:
    """
    Motor de paper trading que simula operaciones en vivo.
    
    Características:
    - Conexión CCXT solo-lectura para datos en tiempo real
    - Estrategia híbrida ONNX (momentum/lateral)
    - Contabilidad completa con comisiones y slippage
    - Dashboard en tiempo real
    - Historial persistente en SQLite
    - Alertas y notificaciones
    """
    
    def __init__(self, initial_capital: float = INITIAL_CAPITAL,
                 symbols: list = None, model_path: str = None,
                 scaler_path: str = None):
        
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        # Estado
        self.positions: Dict[str, PaperPosition] = {}
        self.trades: List[PaperTrade] = []
        self.equity_curve: List[Tuple[datetime, float]] = [(datetime.now(), initial_capital)]
        self.is_running = False
        self.start_time = None
        
        # Modelo ONNX
        self.strategy = self._load_onnx_strategy(model_path, scaler_path)
        
        # Exchange (CCXT solo lectura)
        self.exchange = None
        
        # Base de datos
        self._init_database()
        
        # Buffer de datos para cada símbolo
        self.data_buffers: Dict[str, deque] = {
            s: deque(maxlen=200) for s in self.symbols
        }
        
        logger.info(f"Paper Trading Engine inicializado | Capital: ${initial_capital:,.2f}")
    
    def _load_onnx_strategy(self, model_path: str = None, scaler_path: str = None):
        """Carga la estrategia ONNX"""
        if model_path is None:
            model_path = str(MODEL_DIR / "regime_model.onnx")
        if scaler_path is None:
            scaler_path = str(MODEL_DIR / "scaler.pkl")
        
        class PaperStrategy:
            def __init__(self):
                self.model = None
                self.scaler = None
                
                # Cargar scaler
                if os.path.exists(scaler_path):
                    with open(scaler_path, 'rb') as f:
                        self.scaler = pickle.load(f)
                
                # Cargar modelo ONNX
                if os.path.exists(model_path):
                    try:
                        import onnxruntime as ort
                        sess_options = ort.SessionOptions()
                        sess_options.intra_op_num_threads = 2
                        sess_options.inter_op_num_threads = 2
                        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                        
                        self.model = ort.InferenceSession(
                            model_path, sess_options,
                            providers=['CPUExecutionProvider']
                        )
                        self.input_name = self.model.get_inputs()[0].name
                        logger.info(f"Modelo ONNX cargado: {model_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo cargar ONNX: {e}")
            
            def compute_features(self, df: pd.DataFrame) -> np.ndarray:
                """Calcula features para ONNX"""
                if len(df) < 50:
                    return None
                
                close = df['close'].values
                high = df['high'].values
                low = df['low'].values
                volume = df['volume'].values
                open_p = df['open'].values
                
                close_s = pd.Series(close)
                high_s = pd.Series(high)
                low_s = pd.Series(low)
                volume_s = pd.Series(volume)
                open_s = pd.Series(open_p)
                
                features = {}
                
                # RSI
                delta = close_s.diff()
                gain = delta.clip(lower=0).rolling(14).mean()
                loss = (-delta.clip(upper=0)).rolling(14).mean()
                rs = gain / loss.replace(0, np.nan)
                rsi = 100 - (100 / (1 + rs))
                features['rsi_14'] = rsi.iloc[-1]
                features['rsi_delta'] = rsi.diff().iloc[-1] if len(rsi) > 1 else 0
                
                # ATR
                tr1 = high_s - low_s
                tr2 = (high_s - close_s.shift()).abs()
                tr3 = (low_s - close_s.shift()).abs()
                tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                atr = tr.rolling(14).mean()
                atr_sma = atr.rolling(50).mean()
                features['atr_ratio'] = (atr / atr_sma.replace(0, np.nan)).iloc[-1]
                
                # EMA distance
                ema_9 = close_s.ewm(span=9).mean().iloc[-1]
                ema_21 = close_s.ewm(span=21).mean().iloc[-1]
                features['ema_9_21_dist'] = (ema_9 - ema_21) / close[-1]
                
                # Cuerpo de vela
                body = abs(close[-1] - open_p[-1])
                candle_range = high[-1] - low[-1]
                features['candle_body_pct'] = (body / candle_range * 100) if candle_range > 0 else 0
                
                # Volumen ratio
                vol_sma_20 = volume_s.rolling(20).mean()
                features['volume_ratio'] = (volume[-1] / vol_sma_20.iloc[-1]) if vol_sma_20.iloc[-1] > 0 else 1.0
                
                # BB position
                bb_sma = close_s.rolling(20).mean()
                bb_std = close_s.rolling(20).std()
                bb_upper = bb_sma + 2 * bb_std
                bb_lower = bb_sma - 2 * bb_std
                bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
                features['bb_position'] = ((close[-1] - bb_lower.iloc[-1]) / bb_range) if bb_range > 0 else 0.5
                
                # ADX
                plus_dm = high_s.diff()
                minus_dm = low_s.diff()
                plus_dm[plus_dm < 0] = 0
                minus_dm[minus_dm > 0] = 0
                minus_dm = minus_dm.abs()
                tr_sma = tr.rolling(14).mean()
                plus_di = 100 * (plus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
                minus_di = 100 * (minus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
                dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
                features['adx'] = dx.rolling(14).mean().iloc[-1]
                
                # MACD
                ema_12 = close_s.ewm(span=12).mean()
                ema_26 = close_s.ewm(span=26).mean()
                macd = ema_12 - ema_26
                signal = macd.ewm(span=9).mean()
                features['macd_hist'] = (macd - signal).iloc[-1]
                
                # Stochastic
                k_period = 14
                low_k = low_s.rolling(k_period).min()
                high_k = high_s.rolling(k_period).max()
                k_range = high_k.iloc[-1] - low_k.iloc[-1]
                features['stoch_k'] = 100 * (close[-1] - low_k.iloc[-1]) / k_range if k_range > 0 else 50
                
                fnames = ['rsi_14', 'rsi_delta', 'atr_ratio', 'ema_9_21_dist',
                          'candle_body_pct', 'volume_ratio', 'bb_position',
                          'adx', 'macd_hist', 'stoch_k']
                
                arr = np.array([[features.get(f, 0) for f in fnames]], dtype=np.float32)
                return np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)
            
            def predict(self, df: pd.DataFrame) -> Tuple[str, float]:
                """Predice régimen y confianza"""
                if self.model is None or len(df) < 50:
                    return "LATERAL", 0.5
                
                features = self.compute_features(df)
                if features is None:
                    return "LATERAL", 0.5
                
                if self.scaler is not None:
                    features = self.scaler.transform(features).astype(np.float32)
                
                try:
                    pred = self.model.run(None, {self.input_name: features})[0]
                    prob = pred[0][0]
                    regime = "MOMENTUM" if prob >= 0.5 else "LATERAL"
                    confidence = abs(prob - 0.5) * 2  # [0, 1]
                    return regime, min(confidence, 1.0)
                except:
                    return "LATERAL", 0.5
            
            def generate_signal(self, df: pd.DataFrame) -> Tuple[str, str, float]:
                """Genera señal de trading: (acción, régimen, confianza)"""
                regime, confidence = self.predict(df)
                
                close = df['close']
                current_price = close.iloc[-1]
                
                if regime == "MOMENTUM" and confidence > 0.6:
                    # Momentum: seguir tendencia
                    ma_7 = close.tail(7).mean()
                    ma_21 = close.tail(21).mean()
                    
                    if ma_7 > ma_21 * 1.003:
                        return "BUY", regime, confidence
                    elif ma_7 < ma_21 * 0.997:
                        return "SELL", regime, confidence
                else:
                    # LATERAL: mean reversion
                    bb_sma = close.tail(20).mean()
                    bb_std = close.tail(20).std()
                    bb_lower = bb_sma - 2 * bb_std
                    bb_upper = bb_sma + 2 * bb_std
                    
                    if current_price < bb_lower:
                        return "BUY", regime, confidence * 0.8
                    elif current_price > bb_upper:
                        return "SELL", regime, confidence * 0.8
                
                return "HOLD", regime, confidence
        
        return PaperStrategy()
    
    def _init_database(self):
        """Inicializa base de datos SQLite"""
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        # Tabla de trades
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                price REAL NOT NULL,
                quantity REAL NOT NULL,
                cost REAL NOT NULL,
                commission REAL NOT NULL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                balance_after REAL DEFAULT 0,
                regime TEXT DEFAULT 'LATERAL',
                confidence REAL DEFAULT 0.5,
                strategy TEXT DEFAULT '',
                exit_reason TEXT DEFAULT ''
            )
        """)
        
        # Tabla de equity curve
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS equity_curve (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                equity REAL NOT NULL,
                capital REAL NOT NULL,
                open_pnl REAL DEFAULT 0
            )
        """)
        
        # Tabla de sesiones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                initial_capital REAL NOT NULL,
                final_capital REAL,
                total_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Base de datos inicializada: {DB_PATH}")
    
    def _save_trade(self, trade: PaperTrade):
        """Guarda un trade en la base de datos"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades 
                (timestamp, symbol, side, price, quantity, cost, commission,
                 pnl, pnl_pct, balance_after, regime, confidence, strategy, exit_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.timestamp.isoformat(), trade.symbol, trade.side,
                trade.price, trade.quantity, trade.cost, trade.commission,
                trade.pnl, trade.pnl_pct, trade.balance_after,
                trade.regime, trade.confidence, trade.strategy, trade.exit_reason
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando trade: {e}")
    
    def _save_equity_point(self, timestamp: datetime, equity: float, 
                           capital: float, open_pnl: float = 0):
        """Guarda un punto de equity curve"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO equity_curve (timestamp, equity, capital, open_pnl)
                VALUES (?, ?, ?, ?)
            """, (timestamp.isoformat(), equity, capital, open_pnl))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando equity: {e}")
    
    async def fetch_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Obtiene datos de mercado en tiempo real vía CCXT (solo lectura).
        """
        try:
            import ccxt
            
            if self.exchange is None:
                self.exchange = ccxt.binance({
                    'enableRateLimit': True,
                    'rateLimit': 1200,
                    'options': {'defaultType': 'spot'}
                })
            
            # Obtener últimas 100 velas de 1h
            ohlcv = self.exchange.fetch_ohlcv(symbol, '1h', limit=100)
            
            if not ohlcv:
                return None
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def calculate_position_size(self, symbol: str, price: float, 
                                confidence: float) -> float:
        """Calcula el tamaño de posición basado en riesgo"""
        # Porcentaje base del capital
        base_pct = MAX_POSITION_PCT * confidence
        
        # Ajustar por volatilidad
        position_value = self.current_capital * base_pct
        
        # Calcular cantidad
        quantity = position_value / price if price > 0 else 0
        
        return quantity
    
    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: float, 
                            side: str) -> float:
        """Calcula stop loss dinámico"""
        atr = self._calculate_atr(df)
        
        if side == "BUY":
            sl = entry_price - (atr * 1.5)
        else:
            sl = entry_price + (atr * 1.5)
        
        return sl
    
    def calculate_take_profit(self, entry_price: float, stop_loss: float,
                              side: str) -> float:
        """Calcula take profit (risk:reward 1:2)"""
        risk = abs(entry_price - stop_loss)
        
        if side == "BUY":
            tp = entry_price + (risk * 2)
        else:
            tp = entry_price - (risk * 2)
        
        return tp
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcula ATR actual"""
        if len(df) < period + 1:
            return 0
        
        high = df['high'].values
        low = df['low'].values
        close = df['close'].values
        
        tr1 = high[1:] - low[1:]
        tr2 = np.abs(high[1:] - close[:-1])
        tr3 = np.abs(low[1:] - close[:-1])
        tr = np.maximum(np.maximum(tr1, tr2), tr3)
        
        atr = np.mean(tr[-period:])
        return atr
    
    def open_position(self, symbol: str, side: str, price: float, 
                      df: pd.DataFrame, regime: str, confidence: float) -> Optional[PaperPosition]:
        """Abre una nueva posición paper"""
        if symbol in self.positions:
            logger.warning(f"Ya hay posición abierta en {symbol}")
            return None
        
        # Calcular tamaño
        quantity = self.calculate_position_size(symbol, price, confidence)
        if quantity <= 0:
            return None
        
        # Aplicar slippage
        if side == "BUY":
            exec_price = price * (1 + SLIPPAGE_PCT)
        else:
            exec_price = price * (1 - SLIPPAGE_PCT)
        
        # Calcular costos
        cost = quantity * exec_price
        commission = cost * COMMISSION_RATE
        total_cost = cost + commission
        
        # Verificar capital disponible
        if total_cost > self.current_capital * 0.5:
            logger.warning(f"Capital insuficiente para {symbol}: ${total_cost:.2f} > ${self.current_capital * 0.5:.2f}")
            return None
        
        # Calcular stops
        stop_loss = self.calculate_stop_loss(df, exec_price, side)
        take_profit = self.calculate_take_profit(exec_price, stop_loss, side)
        
        # Crear posición
        position = PaperPosition(
            symbol=symbol,
            side=side,
            entry_price=exec_price,
            quantity=quantity,
            entry_cost=total_cost,
            entry_time=datetime.now(),
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_sl=stop_loss,
            regime=regime,
            confidence=confidence,
        )
        
        self.positions[symbol] = position
        self.current_capital -= total_cost
        
        # Registrar trade de entrada
        trade = PaperTrade(
            timestamp=datetime.now(),
            symbol=symbol,
            side=side,
            price=exec_price,
            quantity=quantity,
            cost=total_cost,
            commission=commission,
            balance_after=self.current_capital,
            regime=regime,
            confidence=confidence,
            strategy=f"ONNX_{regime}",
        )
        self.trades.append(trade)
        self._save_trade(trade)
        
        logger.info(f"📈 POSICIÓN ABIERTA: {side} {quantity:.6f} {symbol} @ ${exec_price:.2f}")
        
        return position
    
    def close_position(self, symbol: str, price: float, reason: str = "MANUAL") -> Optional[PaperTrade]:
        """Cierra una posición paper"""
        if symbol not in self.positions:
            return None
        
        position = self.positions[symbol]
        
        # Aplicar slippage
        if position.side == "BUY":
            exec_price = price * (1 - SLIPPAGE_PCT)
        else:
            exec_price = price * (1 + SLIPPAGE_PCT)
        
        # Calcular P&L
        if position.side == "BUY":
            pnl = (exec_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - exec_price) * position.quantity
        
        # Comisión de salida
        proceeds = position.quantity * exec_price
        commission = proceeds * COMMISSION_RATE
        net_proceeds = proceeds - commission
        
        # Actualizar capital
        self.current_capital += net_proceeds
        pnl_pct = pnl / position.entry_cost * 100 if position.entry_cost > 0 else 0
        
        # Registrar trade de salida
        trade = PaperTrade(
            timestamp=datetime.now(),
            symbol=symbol,
            side='SELL' if position.side == 'BUY' else 'BUY',
            price=exec_price,
            quantity=position.quantity,
            cost=net_proceeds,
            commission=commission,
            pnl=pnl,
            pnl_pct=pnl_pct,
            balance_after=self.current_capital,
            regime=position.regime,
            confidence=position.confidence,
            strategy=f"ONNX_{position.regime}",
            exit_reason=reason,
        )
        self.trades.append(trade)
        self._save_trade(trade)
        
        # Actualizar peak
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital
        
        # Eliminar posición
        del self.positions[symbol]
        
        logger.info(f"📉 POSICIÓN CERRADA: {symbol} | P&L: ${pnl:.2f} ({pnl_pct:.2f}%) | Razón: {reason}")
        
        return trade
    
    def check_positions(self, df_dict: Dict[str, pd.DataFrame]):
        """Verifica stops y condiciones de salida para todas las posiciones"""
        symbols_to_close = []
        
        for symbol, position in list(self.positions.items()):
            if symbol not in df_dict:
                continue
            
            df = df_dict[symbol]
            if df.empty:
                continue
            
            current_price = df['close'].iloc[-1]
            
            # 1. Stop Loss
            if position.side == "BUY" and current_price <= position.stop_loss:
                symbols_to_close.append((symbol, current_price, "STOP_LOSS"))
            elif position.side == "SELL" and current_price >= position.stop_loss:
                symbols_to_close.append((symbol, current_price, "STOP_LOSS"))
            
            # 2. Take Profit
            elif position.side == "BUY" and current_price >= position.take_profit:
                symbols_to_close.append((symbol, current_price, "TAKE_PROFIT"))
            elif position.side == "SELL" and current_price <= position.take_profit:
                symbols_to_close.append((symbol, current_price, "TAKE_PROFIT"))
            
            # 3. Trailing Stop (actualizar si es favorable)
            else:
                if position.side == "BUY":
                    new_trail = current_price * 0.97  # 3% trailing
                    if new_trail > position.trailing_sl:
                        position.trailing_sl = new_trail
                        position.stop_loss = new_trail
                else:
                    new_trail = current_price * 1.03
                    if new_trail < position.trailing_sl:
                        position.trailing_sl = new_trail
                        position.stop_loss = new_trail
        
        # Cerrar posiciones
        for symbol, price, reason in symbols_to_close:
            self.close_position(symbol, price, reason)
    
    def calculate_open_pnl(self) -> float:
        """Calcula P&L no realizado de posiciones abiertas"""
        total_pnl = 0.0
        
        for symbol, position in self.positions.items():
            # Nota: no tenemos precio actual aquí, se pasa externamente
            # Este método requiere precios actualizados
            pass
        
        return total_pnl
    
    def run_cycle(self, df_dict: Dict[str, pd.DataFrame]) -> dict:
        """
        Ejecuta un ciclo completo de paper trading.
        
        Args:
            df_dict: Dict {symbol: DataFrame} con datos de mercado actualizados
            
        Returns:
            Dict con resultados del ciclo
        """
        results = {
            'timestamp': datetime.now(),
            'signals': {},
            'positions_opened': 0,
            'positions_closed': 0,
            'total_pnl': 0,
        }
        
        # 1. Generar señales para cada símbolo
        for symbol in self.symbols:
            if symbol not in df_dict:
                continue
            
            df = df_dict[symbol]
            if df.empty or len(df) < 50:
                continue
            
            # Generar señal
            action, regime, confidence = self.strategy.generate_signal(df)
            results['signals'][symbol] = {
                'action': action,
                'regime': regime,
                'confidence': confidence,
            }
            
            # 2. Ejecutar señal
            current_price = df['close'].iloc[-1]
            
            if action in ('BUY', 'SELL') and symbol not in self.positions:
                self.open_position(symbol, action, current_price, df, regime, confidence)
                results['positions_opened'] += 1
        
        # 3. Verificar posiciones existentes
        self.check_positions(df_dict)
        
        # 4. Calcular equity
        total_equity = self.current_capital
        
        # Valor de posiciones abiertas (estimado)
        for symbol, position in self.positions.items():
            if symbol in df_dict and not df_dict[symbol].empty:
                current_price = df_dict[symbol]['close'].iloc[-1]
                if position.side == "BUY":
                    position_value = position.quantity * current_price
                else:
                    position_value = position.quantity * (2 * position.entry_price - current_price)
                total_equity += position_value
        
        # Guardar equity
        self.equity_curve.append((datetime.now(), total_equity))
        self._save_equity_point(datetime.now(), total_equity, self.current_capital)
        
        results['equity'] = total_equity
        results['capital'] = self.current_capital
        results['open_positions'] = len(self.positions)
        
        return results
    
    def get_stats(self) -> dict:
        """Obtiene estadísticas actuales del paper trading"""
        # Calcular drawdown
        equity_values = [e for _, e in self.equity_curve]
        peak = max(equity_values) if equity_values else self.initial_capital
        current_equity = equity_values[-1] if equity_values else self.initial_capital
        drawdown = (current_equity - peak) / peak * 100 if peak > 0 else 0
        
        # Trades
        closed_trades = [t for t in self.trades if t.exit_reason]
        winning_trades = [t for t in closed_trades if t.pnl > 0]
        losing_trades = [t for t in closed_trades if t.pnl <= 0]
        
        total_pnl = sum(t.pnl for t in closed_trades)
        win_rate = len(winning_trades) / len(closed_trades) if closed_trades else 0
        avg_win = np.mean([t.pnl for t in winning_trades]) if winning_trades else 0
        avg_loss = abs(np.mean([t.pnl for t in losing_trades])) if losing_trades else 1
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0
        
        # Sharpe (aproximado con datos diarios)
        if len(equity_values) > 1:
            returns = np.diff(equity_values) / equity_values[:-1]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(365 * 24) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            'initial_capital': self.initial_capital,
            'current_capital': self.current_capital,
            'current_equity': current_equity,
            'total_pnl': total_pnl,
            'total_return': (current_equity - self.initial_capital) / self.initial_capital * 100,
            'drawdown': drawdown,
            'peak_equity': peak,
            'total_trades': len(closed_trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'open_positions': len(self.positions),
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'run_time': str(datetime.now() - self.start_time) if self.start_time else 'N/A',
        }
    
    def print_dashboard(self):
        """Imprime dashboard en consola"""
        stats = self.get_stats()
        
        print("\n" + "=" * 70)
        print("📋 PAPER TRADING DASHBOARD")
        print("=" * 70)
        
        print(f"\n💰 CAPITAL:")
        print(f"   Inicial:  ${stats['initial_capital']:>10,.2f}")
        print(f"   Actual:   ${stats['current_capital']:>10,.2f}")
        print(f"   Equity:   ${stats['current_equity']:>10,.2f}")
        print(f"   P&L:      ${stats['total_pnl']:>+10,.2f} ({stats['total_return']:>+.2f}%)")
        print(f"   Drawdown: {stats['drawdown']:>+.2f}%")
        
        print(f"\n📊 ESTADÍSTICAS:")
        print(f"   Trades totales: {stats['total_trades']}")
        print(f"   Win Rate:       {stats['win_rate']:.1%}")
        print(f"   Profit Factor:  {stats['profit_factor']:.2f}")
        print(f"   Sharpe Ratio:   {stats['sharpe_ratio']:.2f}")
        print(f"   Avg Win:        ${stats['avg_win']:.2f}")
        print(f"   Avg Loss:       ${stats['avg_loss']:.2f}")
        
        print(f"\n📈 POSICIONES ABIERTAS: {stats['open_positions']}")
        for symbol, pos in self.positions.items():
            print(f"   {symbol}: {pos.side} {pos.quantity:.6f} @ ${pos.entry_price:.2f}")
        
        print(f"\n⏱️  Tiempo de ejecución: {stats['run_time']}")
        print("=" * 70)
    
    def export_results(self):
        """Exporta resultados a CSV"""
        if not self.trades:
            logger.warning("No hay trades para exportar")
            return
        
        # Trades a DataFrame
        trades_data = []
        for t in self.trades:
            trades_data.append({
                'timestamp': t.timestamp,
                'symbol': t.symbol,
                'side': t.side,
                'price': t.price,
                'quantity': t.quantity,
                'cost': t.cost,
                'commission': t.commission,
                'pnl': t.pnl,
                'pnl_pct': t.pnl_pct,
                'balance_after': t.balance_after,
                'regime': t.regime,
                'confidence': t.confidence,
                'strategy': t.strategy,
                'exit_reason': t.exit_reason,
            })
        
        df_trades = pd.DataFrame(trades_data)
        
        # Guardar
        trades_path = REPORTS_DIR / "papertrading_trades.csv"
        df_trades.to_csv(trades_path, index=False)
        
        # Equity curve
        equity_data = []
        for ts, eq in self.equity_curve:
            equity_data.append({'timestamp': ts, 'equity': eq})
        
        df_equity = pd.DataFrame(equity_data)
        equity_path = REPORTS_DIR / "papertrading_equity.csv"
        df_equity.to_csv(equity_path, index=False)
        
        logger.info(f"Resultados exportados: {trades_path}, {equity_path}")
        
        return trades_path, equity_path


async def run_paper_trading_loop(engine: PaperTradingEngine, 
                                  interval_seconds: int = 3600,
                                  max_cycles: int = None):
    """
    Bucle principal de paper trading.
    
    Args:
        engine: PaperTradingEngine instanciado
        interval_seconds: Intervalo entre ciclos (default: 1 hora)
        max_cycles: Máximo de ciclos (None = infinito)
    """
    import asyncio
    
    engine.is_running = True
    engine.start_time = datetime.now()
    cycle_count = 0
    
    logger.info(f"🚀 Paper Trading iniciado | Intervalo: {interval_seconds}s")
    engine.print_dashboard()
    
    try:
        while engine.is_running:
            cycle_count += 1
            print(f"\n{'='*70}")
            print(f"🔄 Ciclo #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*70}")
            
            # Obtener datos de mercado para cada símbolo
            df_dict = {}
            for symbol in engine.symbols:
                print(f"   📥 Obteniendo datos para {symbol}...")
                df = await engine.fetch_market_data(symbol)
                if df is not None:
                    df_dict[symbol] = df
                    print(f"      ✅ {len(df)} velas obtenidas")
                else:
                    print(f"      ❌ Error obteniendo datos")
            
            # Ejecutar ciclo
            if df_dict:
                results = engine.run_cycle(df_dict)
                
                print(f"\n📊 Resultados del ciclo:")
                print(f"   Señales generadas: {len(results['signals'])}")
                print(f"   Posiciones abiertas: {results['positions_opened']}")
                print(f"   Equity actual: ${results['equity']:,.2f}")
                
                # Mostrar señales
                for symbol, signal in results['signals'].items():
                    print(f"   {symbol}: {signal['action']} ({signal['regime']}, conf: {signal['confidence']:.2f})")
            
            # Dashboard
            engine.print_dashboard()
            
            # Verificar máximo de ciclos
            if max_cycles and cycle_count >= max_cycles:
                logger.info(f"Máximo de ciclos alcanzado: {max_cycles}")
                break
            
            # Esperar
            print(f"\n⏳ Esperando {interval_seconds}s para el siguiente ciclo...")
            await asyncio.sleep(interval_seconds)
    
    except KeyboardInterrupt:
        logger.info("Paper trading detenido por usuario")
    except Exception as e:
        logger.error(f"Error en bucle principal: {e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.is_running = False
        
        # Cerrar posiciones abiertas si hay
        for symbol in list(engine.positions.keys()):
            engine.close_position(symbol, 0, "SESSION_END")
        
        # Exportar resultados
        engine.export_results()
        
        # Estadísticas finales
        print("\n" + "=" * 70)
        print("📋 PAPER TRADING FINALIZADO")
        print("=" * 70)
        engine.print_dashboard()
        print("\n✅ Resultados exportados a reports/")
        print("=" * 70)