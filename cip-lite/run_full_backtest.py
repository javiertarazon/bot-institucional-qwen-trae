#!/usr/bin/env python3
"""
🚀 RUN FULL BACKTEST - CIP v2.0
Backtesting profesional unificado con:
- Modelo ONNX para clasificación de régimen
- Split temporal 70/30 SIN SOLAPAMIENTO
- Walk-Forward Analysis
- Out-of-Sample Testing
- Monte Carlo Simulation
- Métricas profesionales completas
- Reporte HTML
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import json
import pickle
import warnings
warnings.filterwarnings("ignore")

# Módulos CIP
from services.backtesting.engine import BacktestEngine, BacktestConfig, Strategy
from services.backtesting.walk_forward import WalkForwardAnalysis, WalkForwardConfig
from services.backtesting.out_of_sample import OutOfSampleTester, OutOfSampleConfig, MarketRegime
from services.backtesting.monte_carlo import MonteCarloSimulator, MonteCarloConfig
from services.backtesting.capacity_turnover import CapacityTurnoverAnalyzer, CapacityTurnoverConfig
from services.backtesting.visualizer import BacktestVisualizer, BacktestReport

# ==================== CONFIGURACIÓN ====================
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "historical"
MODEL_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Símbolos por defecto (top 10 criptos)
DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT",
    "DOGE/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT",
]

# Configuración de backtesting
INITIAL_CAPITAL = 10000.0
COMMISSION_RATE = 0.001  # 0.1%
SLIPPAGE_PCT = 0.0005    # 0.05%
MAX_POSITION_PCT = 0.1   # 10% por posición
RISK_PER_TRADE = 0.02    # 2% riesgo por operación

# Thresholds para métricas
SHARPE_THRESHOLD = 1.0
MAX_DD_THRESHOLD = -0.20
WIN_RATE_THRESHOLD = 0.45


class ONNXRegimeStrategy:
    """
    Estrategia de trading que usa el clasificador ONNX para determinar
    el régimen de mercado y aplicar la estrategia correspondiente.
    
    - MOMENTUM → Estrategia de tendencia (seguir la dirección)
    - LATERAL → Mean reversion o no operar
    """
    
    def __init__(self, model_path: str = None, scaler_path: str = None):
        self.model = None
        self.scaler = None
        self.feature_names = None
        self.load_model(model_path, scaler_path)
    
    def load_model(self, model_path: str = None, scaler_path: str = None):
        """Carga el modelo ONNX y el scaler"""
        if model_path is None:
            model_path = str(MODEL_DIR / "regime_model.onnx")
        if scaler_path is None:
            scaler_path = str(MODEL_DIR / "scaler.pkl")
        
        # Cargar scaler
        if os.path.exists(scaler_path):
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            print(f"   ✅ Scaler cargado: {scaler_path}")
        
        # Cargar modelo ONNX
        if os.path.exists(model_path):
            try:
                import onnxruntime as ort
                sess_options = ort.SessionOptions()
                sess_options.intra_op_num_threads = 2
                sess_options.inter_op_num_threads = 2
                sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                
                self.model = ort.InferenceSession(
                    model_path, sess_options,
                    providers=['CPUExecutionProvider']
                )
                self.input_name = self.model.get_inputs()[0].name
                print(f"   ✅ Modelo ONNX cargado: {model_path}")
            except Exception as e:
                print(f"   ⚠️  No se pudo cargar ONNX: {e}")
                self.model = None
        else:
            print(f"   ⚠️  Modelo ONNX no encontrado: {model_path}")
            print(f"      Entrena primero: python python_brain/train_and_export_onnx.py")
    
    def compute_features(self, df: pd.DataFrame) -> np.ndarray:
        """Calcula features para el modelo ONNX"""
        if len(df) < 50:
            return None
        
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        volume = df['volume'].values
        open_p = df['open'].values
        
        # Convertir a Series para cálculos rolling
        close_s = pd.Series(close)
        high_s = pd.Series(high)
        low_s = pd.Series(low)
        volume_s = pd.Series(volume)
        open_s = pd.Series(open_p)
        
        features = {}
        
        # 1. RSI(14)
        delta = close_s.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        features['rsi_14'] = rsi.iloc[-1]
        features['rsi_delta'] = rsi.diff().iloc[-1] if len(rsi) > 1 else 0
        
        # 2. ATR ratio
        tr1 = high_s - low_s
        tr2 = (high_s - close_s.shift()).abs()
        tr3 = (low_s - close_s.shift()).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr_sma = atr.rolling(50).mean()
        features['atr_ratio'] = (atr / atr_sma.replace(0, np.nan)).iloc[-1]
        
        # 3. EMA distance
        ema_9 = close_s.ewm(span=9).mean().iloc[-1]
        ema_21 = close_s.ewm(span=21).mean().iloc[-1]
        features['ema_9_21_dist'] = (ema_9 - ema_21) / close[-1]
        
        # 4. Cuerpo de vela
        body = abs(close[-1] - open_p[-1])
        candle_range = high[-1] - low[-1]
        features['candle_body_pct'] = (body / candle_range * 100) if candle_range > 0 else 0
        
        # 5. Volumen ratio
        vol_sma_20 = volume_s.rolling(20).mean()
        features['volume_ratio'] = (volume[-1] / vol_sma_20.iloc[-1]) if vol_sma_20.iloc[-1] > 0 else 1.0
        
        # 6. BB position
        bb_sma = close_s.rolling(20).mean()
        bb_std = close_s.rolling(20).std()
        bb_upper = bb_sma + 2 * bb_std
        bb_lower = bb_sma - 2 * bb_std
        bb_range = bb_upper.iloc[-1] - bb_lower.iloc[-1]
        features['bb_position'] = ((close[-1] - bb_lower.iloc[-1]) / bb_range) if bb_range > 0 else 0.5
        
        # 7. ADX
        plus_dm = high_s.diff()
        minus_dm = low_s.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = minus_dm.abs()
        tr_sma = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        features['adx'] = dx.rolling(14).mean().iloc[-1]
        
        # 8. MACD histogram
        ema_12 = close_s.ewm(span=12).mean()
        ema_26 = close_s.ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9).mean()
        features['macd_hist'] = (macd - signal).iloc[-1]
        
        # 9. Stochastic %K
        k_period = 14
        low_k = low_s.rolling(k_period).min()
        high_k = high_s.rolling(k_period).max()
        k_range = high_k.iloc[-1] - low_k.iloc[-1]
        features['stoch_k'] = 100 * (close[-1] - low_k.iloc[-1]) / k_range if k_range > 0 else 50
        
        # Convertir a array en el orden correcto
        feature_names = [
            'rsi_14', 'rsi_delta', 'atr_ratio', 'ema_9_21_dist',
            'candle_body_pct', 'volume_ratio', 'bb_position',
            'adx', 'macd_hist', 'stoch_k'
        ]
        
        feature_array = np.array([[features.get(f, 0) for f in feature_names]], dtype=np.float32)
        
        # Reemplazar NaN/Inf
        feature_array = np.nan_to_num(feature_array, nan=0.0, posinf=1.0, neginf=-1.0)
        
        return feature_array
    
    def predict_regime(self, df: pd.DataFrame) -> str:
        """Predice el régimen de mercado: MOMENTUM o LATERAL"""
        if self.model is None:
            return "LATERAL"  # Default seguro
        
        features = self.compute_features(df)
        if features is None:
            return "LATERAL"
        
        # Normalizar
        if self.scaler is not None:
            features = self.scaler.transform(features).astype(np.float32)
        
        # Inferencia
        try:
            pred = self.model.run(None, {self.input_name: features})[0]
            return "MOMENTUM" if pred[0][0] == 1 else "LATERAL"
        except:
            return "LATERAL"
    
    def __call__(self, data: pd.DataFrame) -> str:
        """
        Genera señal de trading basada en régimen ONNX + estrategia.
        Esta función es la que usa BacktestEngine.
        """
        if len(data) < 50:
            return 'HOLD'
        
        # 1. Predecir régimen
        regime = self.predict_regime(data)
        
        close = data['close']
        
        # 2. Aplicar estrategia según régimen
        if regime == "MOMENTUM":
            # Estrategia de momentum: seguir tendencia
            ma_7 = close.tail(7).mean()
            ma_21 = close.tail(21).mean()
            
            if ma_7 > ma_21 * 1.005:  # Tendencia alcista
                return 'BUY'
            elif ma_7 < ma_21 * 0.995:  # Tendencia bajista
                return 'SELL'
            else:
                return 'HOLD'
        else:
            # LATERAL: mean reversion o no operar
            # Usar Bollinger Bands para detectar sobrecompra/sobreventa
            bb_sma = close.tail(20).mean()
            bb_std = close.tail(20).std()
            bb_upper = bb_sma + 2 * bb_std
            bb_lower = bb_sma - 2 * bb_std
            
            current_price = close.iloc[-1]
            
            if current_price < bb_lower:
                return 'BUY'  # Sobreventa
            elif current_price > bb_upper:
                return 'SELL'  # Sobrecompra
            else:
                return 'HOLD'  # No operar en lateral


def load_data(symbols: list = None) -> pd.DataFrame:
    """Carga datos históricos desde Parquet"""
    if symbols is None:
        symbols = DEFAULT_SYMBOLS
    
    all_dfs = []
    for symbol in symbols:
        parquet_path = DATA_DIR / f"{symbol.replace('/', '_')}.parquet"
        if not parquet_path.exists():
            print(f"   ⚠️  {symbol}: datos no encontrados")
            continue
        
        df = pd.read_parquet(parquet_path)
        if df.empty:
            continue
        
        df['symbol'] = symbol
        all_dfs.append(df)
        print(f"   ✅ {symbol}: {len(df)} velas")
    
    if not all_dfs:
        print("\n❌ No hay datos. Descarga primero:")
        print("   python 01_data_ingestion/historical_downloader.py")
        sys.exit(1)
    
    combined = pd.concat(all_dfs, axis=0)
    combined.sort_index(inplace=True)
    
    print(f"\n📦 Total: {len(combined)} filas, {combined['symbol'].nunique()} símbolos")
    return combined


def run_backtest_per_symbol(data: pd.DataFrame, strategy, symbol: str) -> dict:
    """Ejecuta backtesting para un símbolo específico"""
    print(f"\n📊 Backtesting {symbol}...")
    
    # Filtrar datos del símbolo
    symbol_data = data[data['symbol'] == symbol].copy()
    
    if len(symbol_data) < 100:
        print(f"   ⚠️  Datos insuficientes: {len(symbol_data)} velas")
        return None
    
    # Configurar backtesting
    config = BacktestConfig(
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION_RATE,
        slippage_pct=SLIPPAGE_PCT,
        max_position_pct=MAX_POSITION_PCT,
        risk_per_trade_pct=RISK_PER_TRADE,
    )
    
    engine = BacktestEngine(config)
    results = engine.run(symbol_data, strategy)
    
    print(f"   Trades: {results['total_trades']} | "
          f"Win Rate: {results['win_rate']:.1%} | "
          f"Sharpe: {results['sharpe_ratio']:.2f} | "
          f"Return: {results['total_return']:.2%}")
    
    return results


def run_walk_forward(data: pd.DataFrame, strategy) -> dict:
    """Ejecuta Walk-Forward Analysis"""
    print("\n" + "=" * 60)
    print("🔄 WALK-FORWARD ANALYSIS")
    print("=" * 60)
    
    config = WalkForwardConfig(
        train_window_days=252,   # 1 año
        test_window_days=63,     # 3 meses
        step_days=21,            # 1 mes
        initial_capital=INITIAL_CAPITAL,
        commission_rate=COMMISSION_RATE,
        slippage_pct=SLIPPAGE_PCT,
    )
    
    wf = WalkForwardAnalysis(config)
    results = wf.run(data, strategy)
    
    summary = results['summary']
    print(f"\n📊 Resultados Walk-Forward:")
    print(f"   Ventanas: {summary['num_windows']}")
    print(f"   Retorno medio: {summary['mean_total_return']:.2%}")
    print(f"   Sharpe medio: {summary['mean_sharpe_ratio']:.2f}")
    print(f"   Estabilidad: {summary['stability_ratio']:.2f}")
    print(f"   Worst DD: {summary['worst_max_drawdown']:.2%}")
    
    return results


def run_out_of_sample(data: pd.DataFrame, strategy) -> dict:
    """Ejecuta pruebas Out-of-Sample"""
    print("\n" + "=" * 60)
    print("🧪 OUT-OF-SAMPLE TESTING")
    print("=" * 60)
    
    config = OutOfSampleConfig(
        test_size_pct=0.3,
        num_independent_test_sets=3,
    )
    
    oos = OutOfSampleTester(config)
    results = oos.run(data, strategy)
    
    summary = results['summary']
    print(f"\n📊 Resultados Out-of-Sample:")
    print(f"   Test sets: {summary['num_test_sets']}")
    print(f"   Todos pasaron: {summary['all_test_sets_passed']}")
    print(f"   Retorno medio: {summary['mean_total_return']:.2%}")
    print(f"   Sharpe medio: {summary['mean_sharpe_ratio']:.2f}")
    
    return results


def run_monte_carlo(data: pd.DataFrame) -> dict:
    """Ejecuta simulaciones Monte Carlo"""
    print("\n" + "=" * 60)
    print("🎲 MONTE CARLO SIMULATION")
    print("=" * 60)
    
    config = MonteCarloConfig(
        num_scenarios=10000,
        num_days=252,
        initial_price=data['close'].iloc[-1],
        parallel=True,
        num_workers=4,
    )
    
    mc = MonteCarloSimulator(config)
    results = mc.run(data)
    
    print(f"\n📊 Resultados Monte Carlo:")
    print(f"   Escenarios: {results['num_scenarios']}")
    print(f"   Retorno medio: {results['mean_return']:.2%}")
    print(f"   Mediana: {results['median_return']:.2%}")
    print(f"   VaR 95%: {results['var_95']:.2%}")
    print(f"   CVaR 95%: {results['cvar_95']:.2%}")
    print(f"   Prob. pérdida: {results['loss_probability']:.1%}")
    
    return results


def calculate_professional_metrics(all_results: dict, initial_capital: float) -> dict:
    """Calcula métricas profesionales consolidadas"""
    print("\n" + "=" * 60)
    print("📊 MÉTRICAS PROFESIONALES")
    print("=" * 60)
    
    metrics = {}
    
    # Extraer resultados por símbolo
    symbol_results = {}
    for sym, res in all_results.get('symbols', {}).items():
        if res is not None:
            symbol_results[sym] = res
    
    if not symbol_results:
        print("   ⚠️  No hay resultados para calcular métricas")
        return metrics
    
    # Métricas agregadas
    total_returns = [r['total_return'] for r in symbol_results.values()]
    sharpe_ratios = [r['sharpe_ratio'] for r in symbol_results.values()]
    sortino_ratios = [r['sortino_ratio'] for r in symbol_results.values()]
    max_drawdowns = [r['max_drawdown'] for r in symbol_results.values()]
    win_rates = [r['win_rate'] for r in symbol_results.values()]
    total_trades = sum(r['total_trades'] for r in symbol_results.values())
    
    # Sharpe promedio ponderado
    avg_sharpe = np.mean(sharpe_ratios)
    avg_sortino = np.mean(sortino_ratios)
    avg_win_rate = np.mean(win_rates)
    avg_return = np.mean(total_returns)
    avg_max_dd = np.mean(max_drawdowns)
    
    # Calmar Ratio
    annualized_return = (1 + avg_return) ** (252 / 365) - 1 if avg_return > -1 else 0
    calmar_ratio = annualized_return / abs(avg_max_dd) if avg_max_dd != 0 else 0
    
    # Profit Factor consolidado
    winning_trades = sum(r['winning_trades'] for r in symbol_results.values())
    losing_trades = sum(r['losing_trades'] for r in symbol_results.values())
    total_winning = sum(r.get('avg_win', 0) * r['winning_trades'] for r in symbol_results.values())
    total_losing = sum(r.get('avg_loss', 0) * r['losing_trades'] for r in symbol_results.values())
    profit_factor = total_winning / total_losing if total_losing > 0 else float('inf')
    
    # Expectancy
    expectancy = (avg_win_rate * np.mean([r.get('avg_win', 0) for r in symbol_results.values()]) 
                  - (1 - avg_win_rate) * np.mean([r.get('avg_loss', 0) for r in symbol_results.values()]))
    
    # Recovery Factor
    recovery_factor = avg_return / abs(avg_max_dd) if avg_max_dd != 0 else 0
    
    # Ulcer Index
    ulcer_index = np.sqrt(np.mean(np.array(max_drawdowns) ** 2))
    
    metrics = {
        'total_trades': total_trades,
        'winning_trades': winning_trades,
        'losing_trades': losing_trades,
        'win_rate': avg_win_rate,
        'total_return': avg_return,
        'annualized_return': annualized_return,
        'sharpe_ratio': avg_sharpe,
        'sortino_ratio': avg_sortino,
        'calmar_ratio': calmar_ratio,
        'max_drawdown': avg_max_dd,
        'profit_factor': profit_factor,
        'expectancy': expectancy,
        'recovery_factor': recovery_factor,
        'ulcer_index': ulcer_index,
        'avg_holding_days': np.mean([r.get('avg_holding_time_days', 0) for r in symbol_results.values()]),
        'num_symbols': len(symbol_results),
        'symbols_analyzed': list(symbol_results.keys()),
    }
    
    # Evaluación
    metrics['assessment'] = assess_strategy(metrics)
    
    # Imprimir
    print(f"\n🏆 MÉTRICAS CONSOLIDADAS:")
    print(f"   Símbolos: {metrics['num_symbols']}")
    print(f"   Total Trades: {metrics['total_trades']}")
    print(f"   Win Rate: {metrics['win_rate']:.1%}")
    print(f"   Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
    print(f"   Sortino Ratio: {metrics['sortino_ratio']:.2f}")
    print(f"   Calmar Ratio: {metrics['calmar_ratio']:.2f}")
    print(f"   Retorno Total: {metrics['total_return']:.2%}")
    print(f"   Retorno Anualizado: {metrics['annualized_return']:.2%}")
    print(f"   Max Drawdown: {metrics['max_drawdown']:.2%}")
    print(f"   Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"   Expectancy: {metrics['expectancy']:.4f}")
    print(f"   Recovery Factor: {metrics['recovery_factor']:.2f}")
    print(f"   Ulcer Index: {metrics['ulcer_index']:.4f}")
    print(f"\n📋 Evaluación: {metrics['assessment']['grade']}")
    
    return metrics


def assess_strategy(metrics: dict) -> dict:
    """Evalúa la estrategia con semáforo"""
    score = 0
    details = []
    
    # Sharpe Ratio
    if metrics['sharpe_ratio'] >= 2.0:
        score += 3
        details.append(("Sharpe", "🟢", f"{metrics['sharpe_ratio']:.2f}"))
    elif metrics['sharpe_ratio'] >= 1.0:
        score += 2
        details.append(("Sharpe", "🟡", f"{metrics['sharpe_ratio']:.2f}"))
    elif metrics['sharpe_ratio'] >= 0.5:
        score += 1
        details.append(("Sharpe", "🟠", f"{metrics['sharpe_ratio']:.2f}"))
    else:
        details.append(("Sharpe", "🔴", f"{metrics['sharpe_ratio']:.2f}"))
    
    # Max Drawdown
    if metrics['max_drawdown'] >= -0.10:
        score += 3
        details.append(("Max DD", "🟢", f"{metrics['max_drawdown']:.1%}"))
    elif metrics['max_drawdown'] >= -0.20:
        score += 2
        details.append(("Max DD", "🟡", f"{metrics['max_drawdown']:.1%}"))
    elif metrics['max_drawdown'] >= -0.30:
        score += 1
        details.append(("Max DD", "🟠", f"{metrics['max_drawdown']:.1%}"))
    else:
        details.append(("Max DD", "🔴", f"{metrics['max_drawdown']:.1%}"))
    
    # Win Rate
    if metrics['win_rate'] >= 0.60:
        score += 3
        details.append(("Win Rate", "🟢", f"{metrics['win_rate']:.1%}"))
    elif metrics['win_rate'] >= 0.45:
        score += 2
        details.append(("Win Rate", "🟡", f"{metrics['win_rate']:.1%}"))
    elif metrics['win_rate'] >= 0.35:
        score += 1
        details.append(("Win Rate", "🟠", f"{metrics['win_rate']:.1%}"))
    else:
        details.append(("Win Rate", "🔴", f"{metrics['win_rate']:.1%}"))
    
    # Profit Factor
    if metrics['profit_factor'] >= 2.0:
        score += 3
        details.append(("Profit Factor", "🟢", f"{metrics['profit_factor']:.2f}"))
    elif metrics['profit_factor'] >= 1.5:
        score += 2
        details.append(("Profit Factor", "🟡", f"{metrics['profit_factor']:.2f}"))
    elif metrics['profit_factor'] >= 1.0:
        score += 1
        details.append(("Profit Factor", "🟠", f"{metrics['profit_factor']:.2f}"))
    else:
        details.append(("Profit Factor", "🔴", f"{metrics['profit_factor']:.2f}"))
    
    # Calmar Ratio
    if metrics['calmar_ratio'] >= 2.0:
        score += 3
        details.append(("Calmar", "🟢", f"{metrics['calmar_ratio']:.2f}"))
    elif metrics['calmar_ratio'] >= 1.0:
        score += 2
        details.append(("Calmar", "🟡", f"{metrics['calmar_ratio']:.2f}"))
    elif metrics['calmar_ratio'] >= 0.5:
        score += 1
        details.append(("Calmar", "🟠", f"{metrics['calmar_ratio']:.2f}"))
    else:
        details.append(("Calmar", "🔴", f"{metrics['calmar_ratio']:.2f}"))
    
    # Grade
    max_score = 15
    pct = score / max_score
    
    if pct >= 0.8:
        grade = "🌟 EXCELENTE - Estrategia robusta y rentable"
    elif pct >= 0.6:
        grade = "✅ BUENA - Estrategia aceptable con margen de mejora"
    elif pct >= 0.4:
        grade = "⚠️ REGULAR - Se requieren optimizaciones"
    else:
        grade = "❌ DÉBIL - Estrategia no viable en su estado actual"
    
    return {
        'score': score,
        'max_score': max_score,
        'percentage': pct,
        'grade': grade,
        'details': details,
    }


def generate_html_report(metrics: dict, all_results: dict, output_path: Path):
    """Genera reporte HTML profesional"""
    print("\n" + "=" * 60)
    print("📄 GENERANDO REPORTE HTML")
    print("=" * 60)
    
    assessment = metrics.get('assessment', {})
    details = assessment.get('details', [])
    
    # Tabla de métricas
    metrics_rows = ""
    metric_items = [
        ("Total Trades", f"{metrics.get('total_trades', 0)}", "📊"),
        ("Win Rate", f"{metrics.get('win_rate', 0):.1%}", "🎯"),
        ("Sharpe Ratio", f"{metrics.get('sharpe_ratio', 0):.2f}", "📐"),
        ("Sortino Ratio", f"{metrics.get('sortino_ratio', 0):.2f}", "📐"),
        ("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}", "📏"),
        ("Retorno Total", f"{metrics.get('total_return', 0):.2%}", "💰"),
        ("Retorno Anualizado", f"{metrics.get('annualized_return', 0):.2%}", "📈"),
        ("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2%}", "📉"),
        ("Profit Factor", f"{metrics.get('profit_factor', 0):.2f}", "💎"),
        ("Expectancy", f"{metrics.get('expectancy', 0):.4f}", "🎯"),
        ("Recovery Factor", f"{metrics.get('recovery_factor', 0):.2f}", "🔄"),
        ("Ulcer Index", f"{metrics.get('ulcer_index', 0):.4f}", "🩹"),
    ]
    
    for name, value, icon in metric_items:
        metrics_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{icon} {name}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right; font-weight: bold;">{value}</td>
        </tr>"""
    
    # Semáforo
    traffic_light_rows = ""
    for name, color, value in details:
        traffic_light_rows += f"""
        <tr>
            <td style="padding: 6px;">{name}</td>
            <td style="padding: 6px; text-align: center;">{color}</td>
            <td style="padding: 6px; text-align: right;">{value}</td>
        </tr>"""
    
    # Resultados por símbolo
    symbol_rows = ""
    for sym, res in all_results.get('symbols', {}).items():
        if res is None:
            continue
        symbol_rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #eee;">{sym}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{res['total_trades']}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{res['win_rate']:.1%}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{res['sharpe_ratio']:.2f}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{res['total_return']:.2%}</td>
            <td style="padding: 8px; border-bottom: 1px solid #eee; text-align: right;">{res['max_drawdown']:.2%}</td>
        </tr>"""
    
    # Walk-Forward
    wf = all_results.get('walk_forward', {})
    wf_summary = wf.get('summary', {})
    
    # Monte Carlo
    mc = all_results.get('monte_carlo', {})
    
    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CIP - Backtest Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f0f1a; color: #e0e0e0; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); padding: 40px; border-radius: 15px; margin-bottom: 30px; text-align: center; }}
        .header h1 {{ font-size: 2.2em; color: #e94560; margin-bottom: 10px; }}
        .header .subtitle {{ color: #a0a0b0; font-size: 1.1em; }}
        .grade {{ font-size: 1.3em; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; }}
        .grade-excellent {{ background: linear-gradient(135deg, #1a3a1a, #2a5a2a); border: 1px solid #4caf50; }}
        .grade-good {{ background: linear-gradient(135deg, #1a2a1a, #2a4a2a); border: 1px solid #8bc34a; }}
        .grade-fair {{ background: linear-gradient(135deg, #2a2a1a, #4a4a2a); border: 1px solid #ffc107; }}
        .grade-weak {{ background: linear-gradient(135deg, #2a1a1a, #4a2a2a); border: 1px solid #f44336; }}
        .card {{ background: #1a1a2e; border-radius: 12px; padding: 25px; margin-bottom: 25px; border: 1px solid #2a2a4a; }}
        .card h2 {{ color: #e94560; margin-bottom: 20px; font-size: 1.4em; border-bottom: 2px solid #2a2a4a; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #2a2a4a; padding: 10px; text-align: left; font-weight: 600; color: #a0a0b0; }}
        td {{ padding: 8px; border-bottom: 1px solid #1a1a2e; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
        .grid-3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }}
        .stat-box {{ background: #16213e; padding: 20px; border-radius: 10px; text-align: center; }}
        .stat-box .value {{ font-size: 2em; font-weight: bold; color: #e94560; }}
        .stat-box .label {{ color: #a0a0b0; font-size: 0.9em; margin-top: 5px; }}
        .footer {{ text-align: center; padding: 20px; color: #666; font-size: 0.9em; }}
        @media (max-width: 768px) {{ .grid-2, .grid-3 {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 CIP - Backtest Report</h1>
            <div class="subtitle">Crypto Intelligence Platform v2.0</div>
            <div style="margin-top: 15px; color: #888;">
                {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
                {metrics.get('num_symbols', 0)} símbolos | 
                Capital inicial: ${INITIAL_CAPITAL:,.0f}
            </div>
        </div>
        
        <div class="grade grade-{'excellent' if assessment.get('percentage', 0) >= 0.8 else 'good' if assessment.get('percentage', 0) >= 0.6 else 'fair' if assessment.get('percentage', 0) >= 0.4 else 'weak'}">
            {assessment.get('grade', 'Sin evaluación')}
            <div style="font-size: 0.8em; margin-top: 10px; color: #888;">
                Score: {assessment.get('score', 0)}/{assessment.get('max_score', 15)} ({assessment.get('percentage', 0):.0%})
            </div>
        </div>
        
        <div class="grid-3">
            <div class="stat-box">
                <div class="value">{metrics.get('total_trades', 0)}</div>
                <div class="label">Total Trades</div>
            </div>
            <div class="stat-box">
                <div class="value">{metrics.get('sharpe_ratio', 0):.2f}</div>
                <div class="label">Sharpe Ratio</div>
            </div>
            <div class="stat-box">
                <div class="value">{metrics.get('total_return', 0):.1%}</div>
                <div class="label">Total Return</div>
            </div>
        </div>
        
        <div class="card">
            <h2>📊 Semáforo de Métricas</h2>
            <table>
                <tr><th>Métrica</th><th>Estado</th><th>Valor</th></tr>
                {traffic_light_rows}
            </table>
        </div>
        
        <div class="grid-2">
            <div class="card">
                <h2>📈 Métricas de Rendimiento</h2>
                <table>
                    {metrics_rows}
                </table>
            </div>
            
            <div class="card">
                <h2>🪙 Resultados por Símbolo</h2>
                <table>
                    <tr>
                        <th>Símbolo</th><th>Trades</th><th>Win Rate</th><th>Sharpe</th><th>Return</th><th>Max DD</th>
                    </tr>
                    {symbol_rows}
                </table>
            </div>
        </div>
        
        <div class="card">
            <h2>🔄 Walk-Forward Analysis</h2>
            <div class="grid-3">
                <div class="stat-box">
                    <div class="value">{wf_summary.get('num_windows', 0)}</div>
                    <div class="label">Ventanas</div>
                </div>
                <div class="stat-box">
                    <div class="value">{wf_summary.get('mean_sharpe_ratio', 0):.2f}</div>
                    <div class="label">Sharpe Medio</div>
                </div>
                <div class="stat-box">
                    <div class="value">{wf_summary.get('stability_ratio', 0):.2f}</div>
                    <div class="label">Estabilidad</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>🎲 Monte Carlo Simulation</h2>
            <div class="grid-3">
                <div class="stat-box">
                    <div class="value">{mc.get('num_scenarios', 0):,}</div>
                    <div class="label">Escenarios</div>
                </div>
                <div class="stat-box">
                    <div class="value">{mc.get('var_95', 0):.1%}</div>
                    <div class="label">VaR 95%</div>
                </div>
                <div class="stat-box">
                    <div class="value">{mc.get('loss_probability', 0):.1%}</div>
                    <div class="label">Prob. Pérdida</div>
                </div>
            </div>
        </div>
        
        <div class="footer">
            CIP v2.0 - Generado el {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </div>
    </div>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"   ✅ Reporte HTML generado: {output_path}")
    return output_path


def main():
    """Pipeline completo de backtesting"""
    parser = argparse.ArgumentParser(description="Backtesting profesional CIP v2.0")
    parser.add_argument('--symbols', nargs='+', help='Símbolos a backtestear')
    parser.add_argument('--no-train', action='store_true', help='No reentrenar modelo ONNX')
    parser.add_argument('--quick', action='store_true', help='Modo rápido (sin Walk-Forward ni Monte Carlo)')
    
    args = parser.parse_args()
    
    symbols = args.symbols or DEFAULT_SYMBOLS
    
    print("=" * 70)
    print("🚀 CIP - BACKTESTING PROFESIONAL v2.0")
    print("   ONNX Regime Classifier | Walk-Forward | Monte Carlo")
    print("=" * 70)
    
    print(f"\n📋 Configuración:")
    print(f"   Símbolos: {len(symbols)}")
    print(f"   Capital inicial: ${INITIAL_CAPITAL:,.2f}")
    print(f"   Comisión: {COMMISSION_RATE:.1%}")
    print(f"   Slippage: {SLIPPAGE_PCT:.2%}")
    print(f"   Split temporal: 70% train / 30% backtest")
    
    # 1. Cargar datos
    print("\n📥 Cargando datos históricos...")
    data = load_data(symbols)
    
    # 2. Inicializar estrategia ONNX
    print("\n🧠 Inicializando estrategia ONNX...")
    strategy = ONNXRegimeStrategy()
    
    # 3. Backtesting por símbolo
    print("\n" + "=" * 60)
    print("📊 BACKTESTING POR SÍMBOLO")
    print("=" * 60)
    
    symbol_results = {}
    for symbol in symbols:
        res = run_backtest_per_symbol(data, strategy, symbol)
        if res is not None:
            symbol_results[symbol] = res
    
    all_results = {'symbols': symbol_results}
    
    # 4. Walk-Forward Analysis
    if not args.quick:
        wf_results = run_walk_forward(data, strategy)
        all_results['walk_forward'] = wf_results
    
    # 5. Out-of-Sample Testing
    if not args.quick:
        oos_results = run_out_of_sample(data, strategy)
        all_results['out_of_sample'] = oos_results
    
    # 6. Monte Carlo
    if not args.quick:
        mc_results = run_monte_carlo(data)
        all_results['monte_carlo'] = mc_results
    
    # 7. Métricas profesionales
    metrics = calculate_professional_metrics(all_results, INITIAL_CAPITAL)
    all_results['metrics'] = metrics
    
    # 8. Guardar resultados
    results_path = REPORTS_DIR / "backtest_results.json"
    with open(results_path, 'w') as f:
        # Convertir tipos no serializables
        def json_serialize(obj):
            if isinstance(obj, (np.integer,)): return int(obj)
            if isinstance(obj, (np.floating,)): return float(obj)
            if isinstance(obj, (np.ndarray,)): return obj.tolist()
            if isinstance(obj, (pd.Timestamp,)): return str(obj)
            return str(obj)
        
        json.dump(all_results, f, indent=2, default=json_serialize)
    print(f"\n💾 Resultados guardados: {results_path}")
    
    # 9. Generar reporte HTML
    report_path = REPORTS_DIR / "backtest_report.html"
    generate_html_report(metrics, all_results, report_path)
    
    # 10. Resumen final
    print("\n" + "=" * 70)
    print("✅ BACKTESTING COMPLETADO")
    print("=" * 70)
    print(f"\n📊 Reporte HTML: {report_path}")
    print(f"📊 Datos JSON: {results_path}")
    print(f"\n📋 Resumen:")
    print(f"   Símbolos analizados: {metrics.get('num_symbols', 0)}")
    print(f"   Total trades: {metrics.get('total_trades', 0)}")
    print(f"   Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}")
    print(f"   Retorno total: {metrics.get('total_return', 0):.2%}")
    print(f"   Max Drawdown: {metrics.get('max_drawdown', 0):.2%}")
    print(f"\n📈 Evaluación: {metrics.get('assessment', {}).get('grade', 'N/A')}")
    print(f"\n🚀 Para iniciar paper trading:")
    print(f"   python run_paper_trading.py")
    print("=" * 70)


if __name__ == "__main__":
    main()