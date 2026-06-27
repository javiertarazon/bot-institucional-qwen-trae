#!/usr/bin/env python3
"""
Script de prueba para la estrategia XAUUSD Scalper
Genera datos sintéticos realistas y ejecuta backtest
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from services.strategies import XAUUSDScalper, XAUUSDConfig, XAUUSDBacktest


def generate_realistic_xauusd_data(n_candles: int = 5000, start_price: float = 2350.0) -> pd.DataFrame:
    """
    Genera datos M1 sintéticos pero realistas para XAUUSD.
    Simula: tendencias, volatilidad variable, sesiones (Asia/London/NY).
    """
    np.random.seed(42)

    # Mayor volatilidad base para generar movimientos significativos
    base_returns = np.random.normal(0, 0.001, n_candles)  # ~10 pips std (más alto)

    # Tendencias más fuertes
    trend_changes = np.random.choice([-0.0002, 0, 0.0002], n_candles, p=[0.3, 0.4, 0.3])
    trend = np.cumsum(trend_changes)

    # Ciclos de sesión con más amplitud
    session_cycle = np.sin(np.linspace(0, 30 * np.pi, n_candles)) * 0.002

    # Volatilidad variable (más alta en aperturas)
    volatility = np.ones(n_candles) * 0.001
    spike_points = np.random.choice(n_candles, n_candles // 30, replace=False)
    volatility[spike_points] *= 3  # Picos más frecuentes

    # Generar precios
    prices = start_price + np.cumsum(base_returns * volatility + session_cycle * 0.3 + trend)

    # Crear OHLC con mechas significativas
    candle_range = np.abs(np.random.normal(0.5, 0.3, n_candles))  # Rango de vela variable
    opens = prices + np.random.normal(0, 0.2, n_candles)
    closes = prices + np.random.normal(0, 0.2, n_candles)

    # Velas alcistas/bajistas con cuerpo definido
    bullish = closes > opens
    highs = np.where(bullish, closes + candle_range * 0.3, opens + candle_range * 0.3)
    lows = np.where(bullish, opens - candle_range * 0.5, closes - candle_range * 0.5)

    # Timestamps
    times = pd.date_range(start='2025-06-01 08:00', periods=n_candles, freq='1min')

    df = pd.DataFrame({
        'time': times,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': np.random.randint(100, 1000, n_candles)
    })

    return df


def test_strategy_signal_generation():
    """Prueba la generación de señales"""
    print("\n" + "="*70)
    print("TEST 1: Generación de Señales")
    print("="*70)

    df = generate_realistic_xauusd_data(500)
    config = XAUUSDConfig()
    config.blacklist_hours_utc = []  # Limpiar blacklist para test
    scalper = XAUUSDScalper(config)

    # Probar varias velas
    signals_count = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
    for i in range(50, min(200, len(df))):
        window = df.iloc[:i+1].copy()
        signal = scalper.generate_signal(window, current_spread=15)
        signals_count[signal['signal']] += 1
        if signal['signal'] != 'HOLD':
            print(f"  Vela {i}: {signal['signal']} - {signal.get('reason', 'N/A')}")

    print(f"\nSeñales generadas en 150 velas:")
    print(f"  BUY:  {signals_count['BUY']}")
    print(f"  SELL: {signals_count['SELL']}")
    print(f"  HOLD: {signals_count['HOLD']}")

    assert signals_count['BUY'] + signals_count['SELL'] > 0, "No se generaron señales de trading"
    print("✅ Test 1 PASADO: Señales generadas correctamente")


def test_regime_classification():
    """Prueba clasificación de régimen"""
    print("\n" + "="*70)
    print("TEST 2: Clasificación de Régimen de Mercado")
    print("="*70)

    # Generar datos con alta volatilidad en ciertos segmentos
    np.random.seed(42)
    n = 500

    # Crear segmentos con diferentes características
    df_segments = []
    for i in range(5):
        # Algunos segmentos laterales, otros con momentum
        if i % 2 == 0:
            # Segmento con tendencia clara (MOMENTUM)
            seg_prices = 2350 + np.cumsum(np.random.normal(0.001, 0.002, n // 5))
        else:
            # Segmento lateral
            seg_prices = 2350 + np.random.normal(0, 0.3, n // 5).cumsum()

        seg_opens = seg_prices + np.random.normal(0, 0.2, n // 5)
        seg_closes = seg_prices + np.random.normal(0, 0.2, n // 5)
        seg_highs = np.maximum(seg_opens, seg_closes) + np.abs(np.random.normal(0, 0.5, n // 5))
        seg_lows = np.minimum(seg_opens, seg_closes) - np.abs(np.random.normal(0, 0.5, n // 5))

        df_segments.append(pd.DataFrame({
            'open': seg_opens, 'high': seg_highs,
            'low': seg_lows, 'close': seg_closes
        }))

    df = pd.concat(df_segments, ignore_index=True)

    config = XAUUSDConfig()
    scalper = XAUUSDScalper(config)

    df_ind = scalper.calculate_indicators(df)
    regimes = []
    for i in range(50, min(len(df), len(df_ind))):
        window = df_ind.iloc[:i+1]
        regime = scalper.classify_regime(window)
        regimes.append(regime)

    unique_regimes = set(regimes)
    regime_counts = pd.Series(regimes).value_counts().to_dict()
    print(f"Régimenes detectados: {unique_regimes}")
    print(f"Distribución: {regime_counts}")

    assert len(unique_regimes) >= 2, "Solo se detectó un régimen"
    print("✅ Test 2 PASADO: Múltiples regímenes detectados")


def test_lot_calculation():
    """Prueba cálculo de lotaje"""
    print("\n" + "="*70)
    print("TEST 3: Cálculo de Lotaje")
    print("="*70)

    config = XAUUSDConfig()
    scalper = XAUUSDScalper(config)

    # Con $500 y riesgo 0.20% = $1 USD
    # SL de 100 points ($1 movimiento)
    # Valor por pip por minilot = $1.0
    # Lot = 1.0 / (100 * 1.0) = 0.01

    lot = scalper.calculate_lot_size(500, sl_distance_points=100, pip_value_per_minilot=1.0)
    print(f"  Capital: $500 | Riesgo: 0.20% | SL: 100 points")
    print(f"  Lotaje calculado: {lot}")
    print(f"  Riesgo real: ${lot * 100 * 1.0:.2f}")

    assert 0.01 <= lot <= 0.05, f"Lotaje fuera de rango: {lot}"
    print("✅ Test 3 PASADO: Lotaje dentro de rango seguro")


def test_backtest():
    """Ejecuta backtest completo"""
    print("\n" + "="*70)
    print("TEST 4: Backtest Completo con $500")
    print("="*70)

    df = generate_realistic_xauusd_data(2000)  # ~33 horas de datos M1
    config = XAUUSDConfig()
    backtest = XAUUSDBacktest(config=config, initial_capital=500.0)

    results = backtest.run(df)

    print(f"\n  📊 RESULTADOS DEL BACKTEST:")
    print(f"  {'='*50}")
    print(f"  Capital Inicial:    ${results['initial_capital']:.2f}")
    print(f"  Capital Final:      ${results['final_capital']:.2f}")
    print(f"  Retorno Total:      ${results['total_return_usd']:+.2f} ({results['total_return_pct']:+.2f}%)")
    print(f"  Total Operaciones:  {results['total_trades']}")
    print(f"  Ganadas:            {results['winning_trades']}")
    print(f"  Perdidas:           {results['losing_trades']}")
    print(f"  Win Rate:           {results['win_rate_pct']:.1f}%")
    print(f"  Profit Factor:      {results['profit_factor']:.2f}")
    print(f"  Max Drawdown:       {results['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe Ratio:       {results['sharpe_ratio']:.2f}")
    print(f"  Expectancy/trade:   ${results['expectancy_usd']:+.2f}")

    # Validaciones mínimas
    assert results['total_trades'] > 0, "No se ejecutaron operaciones"
    print("\n✅ Test 4 PASADO: Backtest completado")


if __name__ == "__main__":
    print("\n" + "🧪 "*30)
    print("SUITE DE TESTS - ESTRATEGIA XAUUSD SCALPER")
    print("🧪 "*30)

    try:
        test_strategy_signal_generation()
        test_regime_classification()
        test_lot_calculation()
        test_backtest()

        print("\n" + "="*70)
        print("✅ TODOS LOS TESTS PASADOS EXITOSAMENTE")
        print("="*70)
    except Exception as e:
        print(f"\n❌ ERROR EN TESTS: {e}")
        import traceback
        traceback.print_exc()
