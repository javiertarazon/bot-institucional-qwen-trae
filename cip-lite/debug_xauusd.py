#!/usr/bin/env python3
"""Debug para la estrategia XAUUSD"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime
from services.strategies import XAUUSDScalper, XAUUSDConfig


def generate_realistic_xauusd_data(n_candles=500, start_price=2350.0):
    np.random.seed(42)
    base_returns = np.random.normal(0, 0.0003, n_candles)
    trend = np.cumsum(np.random.normal(0, 0.00005, n_candles))
    prices = start_price + np.cumsum(base_returns + trend)

    opens = prices + np.random.normal(0, 0.1, n_candles)
    closes = prices + np.random.normal(0, 0.1, n_candles)
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 0.5, n_candles))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 0.5, n_candles))

    times = pd.date_range(start='2025-06-01 08:00', periods=n_candles, freq='1min')

    return pd.DataFrame({
        'time': times, 'open': opens, 'high': highs, 'low': lows, 'close': closes
    })


# Generar datos
df = generate_realistic_xauusd_data(300)

# Configurar estrategia
config = XAUUSDConfig()
config.blacklist_hours_utc = []  # Limpiar blacklist
print(f"Blacklist hours: {config.blacklist_hours_utc}")
print(f"Max spread: {config.max_spread_points}")
print(f"Min body: {config.min_candle_body_percent}")

scalper = XAUUSDScalper(config)

# Calcular indicadores para la última vela
df_ind = scalper.calculate_indicators(df)
last = df_ind.iloc[-1]
print(f"\nÚltima vela:")
print(f"  Close: {last['close']:.2f}")
print(f"  Body%: {last['body_pct']:.1f}")
print(f"  RSI: {last['rsi']:.1f}")
print(f"  ATR: {last['atr']:.2f}")
print(f"  EMA9: {last['ema_9']:.2f}")
print(f"  EMA21: {last['ema_21']:.2f}")
print(f"  Trend: {last['trend_strength']:.4f}")

# Hora actual
hour_now = datetime.utcnow().hour
print(f"\nHora UTC actual: {hour_now}")
print(f"En blacklist? {hour_now in config.blacklist_hours_utc}")

# Probar varias velas y ver qué pasa
print("\n=== TEST DE GENERACIÓN DE SEÑALES ===")
for i in range(50, min(100, len(df))):
    window = df.iloc[:i+1].copy()
    signal = scalper.generate_signal(window, current_spread=15)
    if signal['signal'] != 'HOLD':
        print(f"Vela {i}: {signal['signal']} | Reason: {signal.get('reason', 'N/A')} | Regime: {signal.get('regime', 'N/A')}")

# Verificar régimen
print("\n=== CLASIFICACIÓN DE RÉGIMEN ===")
for i in [60, 80, 100, 120, 150]:
    window = df_ind.iloc[:i+1]
    regime = scalper.classify_regime(window)
    print(f"Vela {i}: {regime}")
