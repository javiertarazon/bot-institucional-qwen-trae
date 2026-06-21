#!/usr/bin/env python3
"""
Script para ejecutar backtesting de la estrategia institucional
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import structlog

from services.backtesting.engine import BacktestEngine, BacktestConfig, HistoricalData
from services.ml.institutional_strategy import InstitutionalTradingStrategy

logger = structlog.get_logger()

def main():
    print("=" * 80)
    print("BACKTESTING: ESTRATEGIA INSTITUCIONAL")
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
    
    print(f"\n[1/3] Generando datos históricos de 2 años...")
    data = HistoricalData.generate_synthetic_crypto_data(
        start_date=(datetime.now() - timedelta(days=730)).strftime("%Y-%m-%d"),
        end_date=datetime.now().strftime("%Y-%m-%d"),
        base_price=50000.0,
        volatility=0.02
    )
    
    print(f"[2/3] Ejecutando estrategia institucional...")
    engine = BacktestEngine(config)
    strategy = InstitutionalTradingStrategy(initial_capital=config.initial_capital)
    results = engine.run(data, strategy)
    
    print(f"\n[3/3] Resultados del backtesting:")
    print("-" * 80)
    print(f"Total de operaciones: {results['total_trades']}")
    print(f"Operaciones ganadoras: {results['winning_trades']}")
    print(f"Operaciones perdedoras: {results['losing_trades']}")
    print(f"Tasa de aciertos: {results['win_rate']:.2%}")
    print(f"Rendimiento total: {results['total_return']:.2%}")
    print(f"Rendimiento anualizado: {results['annualized_return']:.2%}")
    print(f"Ratio Sharpe: {results['sharpe_ratio']:.2f}")
    print(f"Ratio Sortino: {results['sortino_ratio']:.2f}")
    print(f"Máximo Drawdown: {results['max_drawdown']:.2%}")
    print(f"Ratio Ganancia/Pérdida: {results['profit_loss_ratio']:.2f}")
    print(f"Ganancia promedio: ${results['avg_win']:.2f}")
    print(f"Pérdida promedio: ${results['avg_loss']:.2f}")
    print("-" * 80)
    
    print("\n✅ Backtesting de estrategia institucional completado!")

if __name__ == "__main__":
    main()
