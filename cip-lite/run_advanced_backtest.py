#!/usr/bin/env python3
"""
Backtesting Estrategia Avanzada vs Línea Base
Fase 5: Validación de mejoras
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
from services.ml.advanced_strategy import AdvancedTradingStrategy
import structlog

logger = structlog.get_logger()

def main():
    print("=" * 80)
    print("Fase 5: COMPARACIÓN LÍNEA BASE VS ESTRATEGIA AVANZADA")
    print("=" * 80)

    # 1. Datos históricos
    print("\n[1/3] Generando datos históricos de 2 años...")
    data = HistoricalData.generate_synthetic_crypto_data("2022-06-01", "2024-06-01")

    # 2. Backtesting línea base
    print("\n[2/3] Ejecutando línea base...")
    config_base = BacktestConfig(initial_capital=100000.0)
    engine_base = BacktestEngine(config_base)
    res_base = engine_base.run(data, Strategy.simple_trend_strategy)

    # 3. Backtesting estrategia avanzada
    print("\n[3/3] Ejecutando estrategia avanzada...")
    config_adv = BacktestConfig(initial_capital=100000.0)
    engine_adv = BacktestEngine(config_adv)
    strategy = AdvancedTradingStrategy()
    res_adv = engine_adv.run(data, strategy)

    # Comparar y mostrar resultados
    print("\n" + "=" * 80)
    print("RESUMEN COMPARATIVO")
    print("=" * 80)
    print(f"{'Métrica':<30} {'Línea Base':<15} {'Avanzada':<15}")
    print("-" * 60)
    metrics = [
        ("Total de operaciones", res_base['total_trades'], res_adv['total_trades']),
        ("Tasa de aciertos", f"{res_base['win_rate']:.2%}", f"{res_adv['win_rate']:.2%}"),
        ("Rendimiento total", f"{res_base['total_return']:.2%}", f"{res_adv['total_return']:.2%}"),
        ("Rendimiento anualizado", f"{res_base['annualized_return']:.2%}", f"{res_adv['annualized_return']:.2%}"),
        ("Ratio Sharpe", f"{res_base['sharpe_ratio']:.2f}", f"{res_adv['sharpe_ratio']:.2f}"),
        ("Máximo Drawdown", f"{res_base['max_drawdown']:.2%}", f"{res_adv['max_drawdown']:.2%}"),
        ("Ratio Ganancia/Pérdida", f"{res_base['profit_loss_ratio']:.2f}", f"{res_adv['profit_loss_ratio']:.2f}")
    ]
    for name, v1, v2 in metrics:
        print(f"{name:<30} {v1:<15} {v2:<15}")

    print("\n" + "=" * 80)
    print("MEJORAS ALCANZADAS")
    print("=" * 80)
    res_base_total = res_base['total_return']
    res_adv_total = res_adv['total_return']
    mejora_pct = 0.0
    if res_base_total != 0:
        mejora_pct = (res_adv_total - res_base_total) / abs(res_base_total)
        print(f"✅ Rendimiento total: {res_base_total:.2%} → {res_adv_total:.2%} (Mejora: {mejora_pct:.1%})")
    else:
        print(f"✅ Rendimiento total: {res_adv_total:.2%}")

    print("\n✅ Fase 5 completada: estrategia avanzada implementada y probada!")
    return res_base, res_adv

if __name__ == "__main__":
    main()
