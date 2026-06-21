#!/usr/bin/env python3
"""
Comparar estrategias: línea base vs mejorada
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import structlog

from services.backtesting.engine import BacktestEngine, BacktestConfig, HistoricalData, Strategy
from services.ml.improved_strategy import ImprovedTrendStrategy
from services.ml.advanced_strategy import AdvancedTradingStrategy

logger = structlog.get_logger()

def main():
    print("=" * 80)
    print("COMPARACIÓN: LÍNEA BASE VS ESTRATEGIAS MEJORADAS")
    print("=" * 80)
    
    # Configuración
    config = BacktestConfig(
        initial_capital=100000.0,
        commission_rate=0.001,
        slippage_pct=0.0005,
        max_position_pct=0.1,
        risk_per_trade_pct=0.02,
        lookback_window=60
    )
    
    print(f"\n[1/4] Generando datos históricos de 2 años...")
    data = HistoricalData.generate_synthetic_crypto_data(
        start_date=(datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d"),
        base_price=50000.0,
        volatility=0.02
    )
    
    # Estrategia 1: Línea base
    print(f"\n[2/4] Ejecutando estrategia línea base...")
    engine1 = BacktestEngine(config)
    results1 = engine1.run(data, Strategy.simple_trend_strategy)
    
    # Estrategia 2: Mejorada
    print(f"\n[3/4] Ejecutando estrategia mejorada...")
    engine2 = BacktestEngine(config)
    strategy2 = ImprovedTrendStrategy()
    results2 = engine2.run(data, strategy2)
    
    # Estrategia 3: Avanzada
    print(f"\n[4/4] Ejecutando estrategia avanzada...")
    engine3 = BacktestEngine(config)
    strategy3 = AdvancedTradingStrategy()
    results3 = engine3.run(data, strategy3)
    
    print("\n" + "=" * 80)
    print("RESUMEN COMPARATIVO")
    print("=" * 80)
    print(f"{'Métrica':<30} {'Línea Base':<15} {'Mejorada':<15} {'Avanzada':<15}")
    print("-" * 80)
    print(f"{'Total de operaciones':<30} {results1['total_trades']:<15} {results2['total_trades']:<15} {results3['total_trades']:<15}")
    print(f"{'Tasa de aciertos':<30} {results1['win_rate']:<15.2%} {results2['win_rate']:<15.2%} {results3['win_rate']:<15.2%}")
    print(f"{'Rendimiento total':<30} {results1['total_return']:<15.2%} {results2['total_return']:<15.2%} {results3['total_return']:<15.2%}")
    print(f"{'Rendimiento anualizado':<30} {results1['annualized_return']:<15.2%} {results2['annualized_return']:<15.2%} {results3['annualized_return']:<15.2%}")
    print(f"{'Ratio Sharpe':<30} {results1['sharpe_ratio']:<15.2f} {results2['sharpe_ratio']:<15.2f} {results3['sharpe_ratio']:<15.2f}")
    print(f"{'Máximo Drawdown':<30} {results1['max_drawdown']:<15.2%} {results2['max_drawdown']:<15.2%} {results3['max_drawdown']:<15.2%}")
    print(f"{'Ratio Ganancia/Pérdida':<30} {results1['profit_loss_ratio']:<15.2f} {results2['profit_loss_ratio']:<15.2f} {results3['profit_loss_ratio']:<15.2f}")
    print("-" * 80)
    
    print("\n✅ Comparación completada!")

if __name__ == "__main__":
    main()
