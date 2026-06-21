#!/usr/bin/env python3
"""
Script principal de backtesting para CIP
Ejecuta el backtest completo y genera el informe final
"""

import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')
import os

from services.backtesting import (
    BacktestEngine,
    BacktestConfig,
    HistoricalData,
    Strategy,
    BacktestVisualizer,
    BacktestReport
)
import structlog

logger = structlog.get_logger()


def main():
    print("=" * 80)
    print("EJECUTANDO BACKTESTING COMPLETO - CIP")
    print("=" * 80)

    # ----------------------------
    # Paso 1: Generar datos históricos (2 años)
    # ----------------------------
    print("\n[1/6] Generando datos históricos de 2 años...")
    start_date = "2022-06-01"
    end_date = "2024-06-01"
    data = HistoricalData.generate_synthetic_crypto_data(start_date, end_date, base_price=50000.0)

    # ----------------------------
    # Paso 2: Configurar motor de backtesting
    # ----------------------------
    print("\n[2/6] Configurando entorno de backtesting...")
    config = BacktestConfig(
        initial_capital=100000.0,
        commission_rate=0.001,  # 0.1%
        slippage_pct=0.0005,    # 0.05%
        max_position_pct=0.1,
        risk_per_trade_pct=0.02
    )
    engine = BacktestEngine(config)

    # ----------------------------
    # Paso 3: Ejecutar backtest sin look-ahead bias
    # ----------------------------
    print("\n[3/6] Ejecutando backtesting...")
    results = engine.run(data, Strategy.simple_trend_strategy)

    # ----------------------------
    # Paso 4: Calcular benchmark (Buy & Hold)
    # ----------------------------
    print("\n[4/6] Calculando benchmark (Buy & Hold)...")
    buy_hold_shares = config.initial_capital / data['Close'].iloc[0]
    benchmark_curve = [config.initial_capital]
    for price in data['Close'].values:
        benchmark_value = price * buy_hold_shares
        benchmark_curve.append(benchmark_value)
    # Ajustar longitud para que coincida con equity curve
    if len(benchmark_curve) > len(results['equity_curve']):
        benchmark_curve = benchmark_curve[:len(results['equity_curve'])]

    # ----------------------------
    # Paso 5: Generar gráficos
    # ----------------------------
    print("\n[5/6] Generando visualizaciones...")
    visualizer = BacktestVisualizer(output_dir="backtest_reports")
    visualizer.plot_equity_curve(results['equity_curve'], benchmark_curve)
    visualizer.plot_drawdown(results['equity_curve'])

    # ----------------------------
    # Paso 6: Generar informe final
    # ----------------------------
    print("\n[6/6] Generando informe final...")
    BacktestReport.generate_text_report(results)

    print("\n" + "=" * 80)
    print("BACKTESTING COMPLETADO!")
    print("=" * 80)
    print("\nResultados clave:")
    print(f"  - Rendimiento total: {results['total_return']:.2%}")
    print(f"  - Tasa de aciertos: {results['win_rate']:.2%}")
    print(f"  - Ratio Sharpe: {results['sharpe_ratio']:.2f}")
    print(f"  - Máximo Drawdown: {results['max_drawdown']:.2%}")
    print("\nInforme y gráficos guardados en la carpeta 'backtest_reports/")


if __name__ == "__main__":
    main()
