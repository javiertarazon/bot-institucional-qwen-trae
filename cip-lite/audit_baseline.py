#!/usr/bin/env python3
"""
Auditoría Integral - Línea Base de Métricas
Fase 5.1: Diagnóstico del rendimiento actual
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
import structlog

logger = structlog.get_logger()

def main():
    print("=" * 80)
    print("AUDITORÍA INTEGRAL - LÍNEA BASE DE MÉTRICAS")
    print("=" * 80)

    # 1. Generar datos históricos
    print("\n[1/3] Generando datos históricos de 2 años...")
    data = HistoricalData.generate_synthetic_crypto_data(
        start_date="2022-06-01",
        end_date="2024-06-01",
        base_price=50000.0
    )

    # 2. Configurar y ejecutar backtesting línea base
    print("\n[2/3] Ejecutando backtesting línea base...")
    config = BacktestConfig(
        initial_capital=100000.0,
        commission_rate=0.001,
        slippage_pct=0.0005,
        max_position_pct=0.1,
        risk_per_trade_pct=0.02
    )
    engine = BacktestEngine(config)
    results_base = engine.run(data, Strategy.simple_trend_strategy)

    # 3. Presentar la línea base
    print("\n" + "=" * 80)
    print("LÍNEA BASE DE MÉTRICAS (Fase 5)")
    print("=" * 80)
    print(f"Total de operaciones: {results_base['total_trades']}")
    print(f"Tasa de aciertos: {results_base['win_rate']:.2%}")
    print(f"Rendimiento total: {results_base['total_return']:.2%}")
    print(f"Rendimiento anualizado: {results_base['annualized_return']:.2%}")
    print(f"Ratio Sharpe: {results_base['sharpe_ratio']:.2f}")
    print(f"Ratio Sortino: {results_base['sortino_ratio']:.2f}")
    print(f"Máximo Drawdown: {results_base['max_drawdown']:.2%}")
    print(f"Ratio Ganancia/Pérdida: {results_base['profit_loss_ratio']:.2f}")
    print(f"Ganancia promedio: ${results_base['avg_win']:.2f}")
    print(f"Pérdida promedio: ${results_base['avg_loss']:.2f}")

    print("\n[3/3] Línea base establecida. Áreas de oportunidad identificadas:")
    print("  1. Mejorar el ratio Sharpe (> 1.0 es objetivo)")
    print("  2. Aumentar el rendimiento anualizado (> 10% objetivo)")
    print("  3. Reducir el máximo drawdown (< 10% objetivo)")

    return results_base

if __name__ == "__main__":
    main()
