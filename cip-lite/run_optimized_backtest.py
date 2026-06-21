#!/usr/bin/env python3
"""
Backtesting de la Estrategia Optimizada
Compara línea base vs estrategia mejorada
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
from services.ml.optimized_predictor import OptimizedStrategy
import structlog

logger = structlog.get_logger()

def main():
    print("=" * 80)
    print("COMPARACIÓN: LÍNEA BASE VS ESTRATEGIA OPTIMIZADA")
    print("=" * 80)

    # 1. Datos
    print("\n[1/4] Generando datos históricos...")
    data = HistoricalData.generate_synthetic_crypto_data("2022-06-01", "2024-06-01")

    # 2. Backtesting línea base
    print("\n[2/4] Ejecutando línea base...")
    config_base = BacktestConfig(initial_capital=100000.0)
    engine_base = BacktestEngine(config_base)
    res_base = engine_base.run(data, Strategy.simple_trend_strategy)

    # 3. Backtesting optimizado
    print("\n[3/4] Ejecutando estrategia optimizada...")
    config_opt = BacktestConfig(
        initial_capital=100000.0)
    engine_opt = BacktestEngine(config_opt)
    opt_strategy = OptimizedStrategy()
    res_opt = engine_opt.run(data, opt_strategy)

    # 4. Comparar resultados
    print("\n" + "=" * 80)
    print("RESULTADOS COMPARATIVOS")
    print("=" * 80)
    print(f"{'Métrica':<30} {'Línea Base':<15} {'Mejorada':<15}")
    print("-" * 60)
    metrics = [
        ("Total de operaciones", res_base['total_trades'], res_opt['total_trades']),
        ("Tasa de aciertos", f"{res_base['win_rate']:.2%}", f"{res_opt['win_rate']:.2%}"),
        ("Rendimiento total", f"{res_base['total_return']:.2%}", f"{res_opt['total_return']:.2%}"),
        ("Rendimiento anualizado", f"{res_base['annualized_return']:.2%}", f"{res_opt['annualized_return']:.2%}"),
        ("Ratio Sharpe", f"{res_base['sharpe_ratio']:.2f}", f"{res_opt['sharpe_ratio']:.2f}"),
        ("Máximo Drawdown", f"{res_base['max_drawdown']:.2%}", f"{res_opt['max_drawdown']:.2%}"),
        ("Ratio Ganancia/Pérdida", f"{res_base['profit_loss_ratio']:.2f}", f"{res_opt['profit_loss_ratio']:.2f}")
    ]
    for name, v1, v2 in metrics:
        print(f"{name:<30} {v1:<15} {v2:<15}")

    print("\n" + "=" * 80)
    print("MEJORAS ALCANZADAS")
    print("=" * 80)
    res_base_total = res_base['total_return']
    res_opt_total = res_opt['total_return']
    if res_base_total != 0:
        mejora = (res_opt_total - res_base_total) / abs(res_base_total)
        print(f"Mejora en rendimiento total: {mejora:.1%}")
    else:
        mejora = 0.0

if __name__ == "__main__":
    main()
