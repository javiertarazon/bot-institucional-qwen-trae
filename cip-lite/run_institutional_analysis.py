#!/usr/bin/env python3
"""
Script de Prueba End-to-End para Análisis Institucional
Integra: Walk-Forward, Monte Carlo, Out-of-Sample, Capacidad y Turnover
"""

import sys
import os
from pathlib import Path

# Añadir el directorio al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from services.backtesting import (
    HistoricalData,
    Strategy,
    WalkForwardAnalysis,
    WalkForwardConfig,
    MonteCarloSimulator,
    MonteCarloConfig,
    OutOfSampleTester,
    OutOfSampleConfig,
    CapacityTurnoverAnalyzer,
    CapacityTurnoverConfig
)
import structlog

logger = structlog.get_logger()


def main():
    """Función principal"""
    print("=" * 80)
    print("ANÁLISIS INSTITUCIONAL COMPLETO")
    print("=" * 80)
    
    # 1. Generar datos históricos
    print("\n[1/5] Generando datos históricos...")
    data = HistoricalData.generate_synthetic_crypto_data(
        start_date="2020-01-01",
        end_date="2024-01-01",
        base_price=50000.0,
        volatility=0.02
    )
    print(f"Datos generados: {len(data)} días")
    
    # 2. Estrategia simple
    strategy = Strategy.simple_trend_strategy
    
    # 3. Análisis Walk-Forward
    print("\n[2/5] Ejecutando Walk-Forward Analysis...")
    wf_config = WalkForwardConfig(
        train_window_days=252,
        test_window_days=63,
        step_days=21
    )
    wf_analyzer = WalkForwardAnalysis(wf_config)
    wf_results = wf_analyzer.run(data, strategy)
    print(f"Walk-Forward completado: {wf_results['summary']['num_windows']} ventanas")
    print(f"Rendimiento acumulado: {wf_results['summary']['total_return_acumulado']:.2%}")
    wf_analyzer.export_report(project_root / "backtest_reports" / "walk_forward_report.csv")
    
    # 4. Simulaciones Monte Carlo
    print("\n[3/5] Ejecutando Simulaciones Monte Carlo...")
    mc_config = MonteCarloConfig(
        num_scenarios=1000,  # Reducido para velocidad
        num_days=252,
        initial_price=data['Close'].iloc[-1]
    )
    mc_simulator = MonteCarloSimulator(mc_config)
    mc_results = mc_simulator.run(data)
    print(f"Monte Carlo completado: {mc_config.num_scenarios} escenarios")
    print(f"Rendimiento medio: {mc_results['mean_return']:.2%}")
    print(f"VaR 95%: {mc_results['var_95']:.2%}")
    mc_simulator.export_scenarios(project_root / "backtest_reports" / "monte_carlo_scenarios.csv")
    
    # 5. Pruebas Out-of-Sample
    print("\n[4/5] Ejecutando Pruebas Out-of-Sample...")
    oos_config = OutOfSampleConfig(
        test_size_pct=0.2,
        num_independent_test_sets=2
    )
    oos_tester = OutOfSampleTester(oos_config)
    oos_results = oos_tester.run(data, strategy)
    print(f"Out-of-Sample completado: {oos_results['summary']['num_test_sets']} conjuntos")
    print(f"Todos pasan umbrales: {oos_results['summary']['all_test_sets_passed']}")
    oos_tester.export_report(project_root / "backtest_reports" / "out_of_sample_report.csv")
    
    # 6. Capacidad y Turnover
    print("\n[5/5] Analizando Capacidad y Turnover...")
    ct_config = CapacityTurnoverConfig(
        base_capital=100000.0
    )
    ct_analyzer = CapacityTurnoverAnalyzer(ct_config)
    ct_results = ct_analyzer.run(data, strategy)
    print(f"Capacidad máxima: ${ct_results['capacity_metrics']['max_capacity']:,.2f}")
    print(f"Turnover anualizado: {ct_results['turnover_metrics']['annualized_turnover_pct']:.2f}%")
    ct_analyzer.export_report(project_root / "backtest_reports" / "capacity_turnover_report.csv")
    
    # Resumen final
    print("\n" + "=" * 80)
    print("ANÁLISIS COMPLETADO")
    print("=" * 80)
    print("\nReportes generados en backtest_reports/:")
    print("  - walk_forward_report.csv")
    print("  - monte_carlo_scenarios.csv")
    print("  - out_of_sample_report_test_sets.csv")
    print("  - out_of_sample_report_regimes.csv")
    print("  - capacity_turnover_report_turnover.csv")
    print("  - capacity_turnover_report_capacity.csv")


if __name__ == "__main__":
    main()
