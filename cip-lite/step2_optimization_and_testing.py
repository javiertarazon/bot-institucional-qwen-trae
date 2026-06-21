#!/usr/bin/env python3
"""
PASOS 2-5: Optimización, Mejoras Estructurales, Pruebas
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

from services.backtesting import BacktestEngine, BacktestConfig, HistoricalData, Strategy
from services.ml.enhanced_strategy import EnhancedTradingStrategy
import numpy as np
import pandas as pd
import structlog
import itertools

logger = structlog.get_logger()

def generate_3y_data():
    start_date = "2021-06-21"
    end_date = "2024-06-21"
    dates = pd.date_range(start=start_date, end=end_date, freq='D')
    n = len(dates)
    np.random.seed(42)
    base_price = 30000

    def create_segment(start_val, length, trend, vol):
        segment = [start_val]
        for _ in range(length-1):
            change = trend + np.random.normal(0, vol)
            next_val = segment[-1] * (1 + change)
            segment.append(max(1000, next_val))
        return segment

    seg1 = create_segment(base_price, 365, 0.0008, 0.03)
    seg2 = create_segment(seg1[-1], 365, -0.0002, 0.05)
    seg3 = create_segment(seg2[-1], 367, 0.0006, 0.025)
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

def calculate_metrics(results):
    max_dd = abs(results['max_drawdown']) if results['max_drawdown'] != 0 else 0.01
    recovery_factor = results['total_return'] / max_dd if max_dd != 0 else 0
    return {
        'roi': results['total_return'],
        'annualized_roi': results['annualized_return'],
        'win_rate': results['win_rate'],
        'max_drawdown': results['max_drawdown'],
        'sharpe': results['sharpe_ratio'],
        'sortino': results['sortino_ratio'],
        'recovery_factor': recovery_factor,
        'profit_loss_ratio': results['profit_loss_ratio'],
        'total_trades': results['total_trades'],
        'avg_win': results['avg_win'],
        'avg_loss': results['avg_loss']
    }

def run_single_backtest(data, strategy_obj):
    config = BacktestConfig(
        initial_capital=100000,
        commission_rate=0.001,
        slippage_pct=0.0005,
        max_position_pct=0.12,
        risk_per_trade_pct=0.02
    )
    engine = BacktestEngine(config)
    results = engine.run(data, strategy_obj)
    return calculate_metrics(results), results

def grid_search_optimization(data):
    print("\n🔍 Iniciando Grid Search de hiperparámetros...")

    # Espacio de búsqueda reducido para eficiencia
    param_grid = {
        'ma_short_win': [5,7,10],
        'ma_long_win': [20,30,40],
        'rsi_oversold': [25,30,35],
        'stop_loss_pct': [0.015,0.02],
        'take_profit_pct': [0.035,0.04,0.045],
        'base_position_pct': [0.08,0.10,0.12]
    }

    best_score = -1.0
    best_params = None
    best_metrics = None
    all_results = []

    keys, values = zip(*param_grid.items())
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
    total = len(combinations)

    for i, params in enumerate(combinations):
        if i % 50 ==0:
            print(f"Progreso: {i}/{total}")

        strategy = EnhancedTradingStrategy(
            ma_short_win=params['ma_short_win'],
            ma_long_win=params['ma_long_win'],
            rsi_oversold=params['rsi_oversold'],
            stop_loss_pct=params['stop_loss_pct'],
            take_profit_pct=params['take_profit_pct'],
            base_position_pct=params['base_position_pct']
        )
        metrics, raw_results = run_single_backtest(data, strategy)

        # Función de puntuación combinada (prioriza Sharpe, ROI, drawdown)
        score = (
            (metrics['sharpe'] if metrics['sharpe'] > -10 else -10) * 0.4 +
            metrics['roi'] * 100 * 0.3 +
            (-metrics['max_drawdown'] * 100) * 0.2 +
            (metrics['win_rate'] *100) *0.1
        )

        all_results.append({**params, **metrics, 'score': score})
        if score > best_score:
            best_score = score
            best_params = params
            best_metrics = metrics

    print("\n✅ Grid Search completado!")
    print(f"\nMejores parámetros: {best_params}")
    print(f"Mejor puntuación combinada: {best_score:.4f}")
    return pd.DataFrame(all_results), best_params, best_metrics

def main():
    print("="*80)
    print("OPTIMIZACIÓN Y PRUEBAS INTEGRALES")
    print("="*80)

    # Datos
    data = generate_3y_data()

    # 1. Línea base (para comparar)
    print("\n" + "-"*80)
    print("1. EJECUTANDO LÍNEA BASE (ESTRATEGIA SIMPLE)")
    print("-"*80)
    baseline_metrics, _ = run_single_backtest(data, Strategy.simple_trend_strategy)

    # 2. Optimización grid search
    print("\n" + "-"*80)
    print("2. OPTIMIZACIÓN DE PARÁMETROS (GRID SEARCH)")
    print("-"*80)
    results_df, best_params, best_metrics = grid_search_optimization(data)

    # 3. Pruebas con la estrategia mejorada (mejores parámetros)
    print("\n" + "-"*80)
    print("3. EJECUTANDO ESTRATEGIA MEJORADA CON MEJORES PARÁMETROS")
    print("-"*80)
    best_strategy = EnhancedTradingStrategy(**best_params)
    final_metrics, final_raw = run_single_backtest(data, best_strategy)

    # 4. Imprimir comparación final
    print("\n" + "="*80)
    print("📊 COMPARACIÓN DE MÉTRICAS")
    print("="*80)
    print(f"{'Métrica':<30} {'Línea Base':<15} {'Mejorada':<15} {'Mejora %':<10}")
    print("-"*80)

    metric_keys = [
        ('roi', 'ROI Acumulado', '%'),
        ('annualized_roi', 'ROI Anualizado', '%'),
        ('win_rate', 'Win Rate', '%'),
        ('max_drawdown', 'Max Drawdown', '%'),
        ('sharpe', 'Ratio Sharpe', ''),
        ('sortino', 'Ratio Sortino', ''),
        ('recovery_factor', 'Factor Recuperación', ''),
        ('profit_loss_ratio', 'Ratio G/P', ''),
        ('total_trades', 'Total Operaciones', ''),
    ]

    for key, label, suffix in metric_keys:
        base = baseline_metrics[key]
        improv = final_metrics[key]
        if suffix == '%':
            base_str = f"{base:.2%}"
            improv_str = f"{improv:.2%}"
        else:
            base_str = f"{base:.2f}"
            improv_str = f"{improv:.2f}"

        # Calcular mejora
        if key in ['max_drawdown']:
            # Mejorar drawdown = reducirlo
            if base !=0:
                pct = ((base - improv) / abs(base))*100
            else:
                pct = 0 if improv ==0 else 100
            pct_str = f"{pct:.1f}%" if pct >0 else "-"
        else:
            if base != 0:
                pct = ((improv - base)/abs(base))*100
            else:
                pct = 100 if improv >0 else 0
            pct_str = f"{pct:.1f}%" if pct >0 else "-"

        print(f"{label:<30} {base_str:<15} {improv_str:<15} {pct_str:<10}")

    # 5. Guardar resultados
    print("\n" + "="*80)
    output_file = "/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite/optimization_results.csv"
    results_df.to_csv(output_file, index=False)
    print(f"Resultados de optimización guardados en: {output_file}")
    print("="*80)

if __name__ == "__main__":
    main()
