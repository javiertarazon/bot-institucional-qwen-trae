#!/usr/bin/env python3
"""
Pruebas de sensibilidad para la estrategia
Varía parámetros clave para evaluar robustez y evitar sobreajuste
"""

import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
import structlog
import pandas as pd

logger = structlog.get_logger()


def sensitivity_analysis():
    print("="*80)
    print("PRUEBAS DE SENSIBILIDAD")
    print("="*80)

    # Datos históricos
    data = HistoricalData.generate_synthetic_crypto_data("2022-06-01", "2024-06-01")

    # Parámetros a variar
    commission_rates = [0.0005, 0.001, 0.002]
    slippage_rates = [0.0002, 0.0005, 0.001]
    position_limits = [0.05, 0.1, 0.2]

    results = []

    for commission in commission_rates:
        for slippage in slippage_rates:
            for pos_limit in position_limits:
                print(f"\nProbando: comisión {commission:.2%}, slippage {slippage:.2%}, pos limit {pos_limit:.0%}")
                config = BacktestConfig(
                    commission_rate=commission,
                    slippage_pct=slippage,
                    max_position_pct=pos_limit
                )
                engine = BacktestEngine(config)
                res = engine.run(data, Strategy.simple_trend_strategy)
                results.append({
                    'commission_rate': commission,
                    'slippage_pct': slippage,
                    'max_position_pct': pos_limit,
                    'total_return': res['total_return'],
                    'sharpe_ratio': res['sharpe_ratio'],
                    'max_drawdown': res['max_drawdown'],
                    'win_rate': res['win_rate']
                })

    # Guardar resultados de sensibilidad
    df_sensitivity = pd.DataFrame(results)
    df_sensitivity.to_csv("backtest_reports/sensitivity_analysis.csv", index=False)
    print("\n" + "="*80)
    print("Pruebas de sensibilidad completadas!")
    print("Resultados guardados en backtest_reports/sensitivity_analysis.csv")
    print(df_sensitivity.round(4))


if __name__ == "__main__":
    sensitivity_analysis()
