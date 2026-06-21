#!/usr/bin/env python3
"""
PASO 1: Análisis inicial de métricas existentes - Línea base de referencia
Genera 3 años de datos y calcula todas las métricas clave
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger()

def generate_3y_data():
    """Genera 3 años de datos con diferentes escenarios: tendencia, volatilidad alta, lateral"""
    print("\nGenerando 3 años de datos históricos (2021-06-21 a 2024-06-21)...")
    start_date = "2021-06-21"
    end_date = "2024-06-21"
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    n = len(dates)

    # Segmentos: 2021 tendencia alcista, 2022 volatilidad alta (bajista), 2023 lateral/alcista
    np.random.seed(42)
    base_price = 30000

    def create_segment(start_val, length, trend, vol):
        segment = [start_val]
        for _ in range(length-1):
            change = trend + np.random.normal(0, vol)
            next_val = segment[-1] * (1 + change)
            segment.append(max(1000, next_val))
        return segment

    # Segmentos: 365 + 365 + 367 = 1097 días (2021-2024 inclusive)
    seg1 = create_segment(base_price, 365, 0.0008, 0.03)  # 2021
    seg2 = create_segment(seg1[-1], 365, -0.0002, 0.05) # 2022
    seg3 = create_segment(seg2[-1], 367, 0.0006, 0.025)# 2023-2024
    prices = np.concatenate([seg1, seg2, seg3])

    df = pd.DataFrame({
        'Date': dates,
        'Open': prices * (1 - np.random.uniform(0, 0.01, n)),
        'High': prices * (1 + np.random.uniform(0, 0.035, n)),
        'Low': prices * (1 - np.random.uniform(0, 0.035, n)),
        'Close': prices,
        'Volume': np.random.randint(10000, 200000, n)
    })
    df.set_index('Date', inplace=True)
    df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
    df = df.dropna()
    return df

def run_baseline_backtest():
    # Configuración base
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.001,
        slippage_pct=0.0005,
        max_position_pct=0.10,
        risk_per_trade_pct=0.02
    )
    engine = BacktestEngine(config)
    data = generate_3y_data()
    results = engine.run(data, Strategy.simple_trend_strategy)

    # Calcular factor de recuperación
    max_dd = abs(results['max_drawdown'])
    recovery_factor = results['total_return'] / max_dd if max_dd > 0 else 0

    # Imprimir línea base
    print("\n" + "="*80)
    print("📊 LÍNEA BASE DE MÉTRICAS")
    print("="*80)
    print(f"1. Capital Inicial: ${config.initial_capital:,.2f}")
    print(f"2. Capital Final: ${config.initial_capital*(1+results['total_return']):,.2f}")
    print(f"3. ROI/PNL Acumulado: {results['total_return']:,.2%}")
    print(f"4. ROI Anualizado: {results['annualized_return']:,.2%}")
    print(f"5. Win Rate: {results['win_rate']:,.2%}")
    print(f"6. Total Operaciones: {results['total_trades']}")
    print(f"7. Operaciones Ganadoras: {results['winning_trades']}")
    print(f"8. Operaciones Perdedoras: {results['losing_trades']}")
    print(f"9. Máximo Drawdown: {results['max_drawdown']:,.2%}")
    print(f"10. Ratio Sharpe: {results['sharpe_ratio']:,.2f}")
    print(f"11. Ratio Sortino: {results['sortino_ratio']:,.2f}")
    print(f"12. Factor de Recuperación: {recovery_factor:,.2f}")
    print(f"13. Ratio Ganancia/Pérdida: {results['profit_loss_ratio']:,.2f}")
    print(f"14. Ganancia Promedio/Operación: ${results['avg_win']:,.2f}")
    print(f"15. Pérdida Promedio/Operación: ${results['avg_loss']:,.2f}")
    print("="*80)

    return results, data

if __name__ == "__main__":
    baseline_results, baseline_data = run_baseline_backtest()
