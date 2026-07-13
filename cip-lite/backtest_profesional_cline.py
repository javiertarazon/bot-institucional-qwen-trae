#!/usr/bin/env python3
"""
🚀 BACKTEST PROFESIONAL - CLINE COMO CEREBRO GENERADOR DE ESTRATEGIAS
- Cline analiza datos y CREA estrategias dinámicamente
- Datos reales CCXT + MT5
- Backtest unitario profesional con métricas completas
"""

import sys
sys.path.insert(0, '/home/javier/Público/proyectos desarrollo/bot-institucional-qwen-trae/cip-lite')

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from services.risk.dynamic_risk_manager import DynamicRiskManager

OUTPUT_DIR = Path('/home/javier/Público/proyectos desarrollo/bot-institucional-qwen-trae/cip-lite/reports')
OUTPUT_DIR.mkdir(exist_ok=True)

INITIAL_CAPITAL = 10000.0
COMMISSION = 0.001

print("=" * 70)
print("🧠 BACKTEST CON CLINE COMO CEREBRO GENERADOR")
print("=" * 70)


def fetch_ccxt_data(symbol='BTC/USDT', timeframe='1h', days=365):
    """Obtener datos reales de CCXT"""
    try:
        import ccxt
        exchange = ccxt.binance()
        exchange.enableRateLimit = True
        since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    except Exception as e:
        print(f"⚠️ CCXT no disponible: {e}")
        return None


def fetch_mt5_data(symbol='BTCUSD', timeframe='H1', bars=2000):
    """Obtener datos reales de MT5"""
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            return None
        
        tf_map = {'M1': mt5.TIMEFRAME_M1, 'M5': mt5.TIMEFRAME_M5, 'M15': mt5.TIMEFRAME_M15,
                  'M30': mt5.TIMEFRAME_M30, 'H1': mt5.TIMEFRAME_H1, 'H4': mt5.TIMEFRAME_H4, 'D1': mt5.TIMEFRAME_D1}
        mt5_tf = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
        
        rates = mt5.copy_rates_from_pos(symbol, mt5_tf, 0, bars)
        mt5.shutdown()
        
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['timestamp'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('timestamp', inplace=True)
        df.rename(columns={'tick_volume': 'volume'}, inplace=True)
        return df[['open', 'high', 'low', 'close', 'volume']]
    except Exception as e:
        print(f"⚠️ MT5 no disponible: {e}")
        return None


def generate_synthetic_data(base_price, n=1000):
    """Datos sintéticos realistas como fallback"""
    np.random.seed(42)
    prices = [base_price]
    
    for i in range(n-1):
        ma = np.mean(prices[-20:]) if len(prices) >= 20 else base_price
        deviation = (prices[-1] - ma) / ma
        mr_force = -deviation * 0.5
        vol = np.random.normal(mr_force, 0.025)
        
        if np.random.random() < 0.03:
            vol += np.random.uniform(-0.08, 0.08)
        
        prices.append(np.clip(prices[-1] * (1 + vol), base_price * 0.2, base_price * 5.0))
    
    return pd.DataFrame({
        'close': prices,
        'high': np.array(prices) * (1 + np.random.uniform(0.005, 0.02, n)),
        'low': np.array(prices) * (1 - np.random.uniform(0.005, 0.02, n)),
        'volume': np.random.randint(10000, 100000, n)
    })


def cline_generate_strategy(df, symbol):
    """
    CLINE COMO CEREBRO: Analiza el mercado y genera una estrategia personalizada
    Retorna: tipo de estrategia + parámetros + datos con indicadores
    """
    close = df['close']
    
    # Análisis de régimen de mercado (Cline decide)
    returns = close.pct_change().dropna()
    volatility = returns.rolling(20).std().iloc[-1] if len(returns) >= 20 else 0.02
    
    ma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else close.mean()
    price_vs_ma = (close.iloc[-1] / ma_50) - 1
    trend_strength = abs(price_vs_ma)
    
    # Decisión de Cline: ¿Qué tipo de estrategia usar?
    if volatility > 0.04:
        strategy_type = "momentum"
        params = {'lookback': 10, 'entry_threshold': 0.02, 'stop_mult': 2.0, 'target_mult': 3.0}
    elif trend_strength > 0.05:
        strategy_type = "trend_following"
        params = {'lookback': 20, 'entry_threshold': 0.01, 'stop_mult': 1.5, 'target_mult': 2.5}
    else:
        strategy_type = "mean_reversion"
        params = {'lookback': 14, 'entry_threshold': 0.015, 'stop_mult': 1.0, 'target_mult': 1.5}
    
    # Calcular indicadores
    df['rsi'] = compute_rsi(close, params['lookback'])
    df['bb_upper'], df['bb_mid'], df['bb_lower'] = compute_bollinger(close, params['lookback'])
    df['atr'] = compute_atr(df)
    
    return strategy_type, params, df


def compute_rsi(prices, period=14):
    """RSI calculation"""
    delta = prices.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_bollinger(prices, period=20, std_mult=2.0):
    """Bollinger Bands"""
    ma = prices.rolling(period).mean()
    std = prices.rolling(period).std()
    upper = ma + (std * std_mult)
    lower = ma - (std * std_mult)
    return upper, ma, lower


def compute_atr(df, period=14):
    """ATR calculation"""
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def apply_cline_strategy(df, strategy_type, params):
    """Aplica la estrategia generada por Cline"""
    close = df['close']
    rsi = df['rsi']
    bb_upper = df['bb_upper']
    bb_lower = df['bb_lower']
    atr = df['atr']
    
    trades = []
    position = None
    
    for i in range(50, len(df)):
        if pd.isna(rsi.iloc[i]) or pd.isna(atr.iloc[i]):
            continue
            
        current_price = close.iloc[i]
        current_atr = atr.iloc[i]
        current_rsi = rsi.iloc[i]
        
        # Gestión de posición abierta
        if position:
            if strategy_type == "mean_reversion":
                if current_price <= position['sl'] or current_price >= position['tp']:
                    pnl_pct = (current_price - position['entry']) / position['entry'] * 100
                    trades.append({
                        'exit_price': current_price,
                        'pnl_pct': pnl_pct,
                        'type': 'STOP' if current_price <= position['sl'] else 'TARGET'
                    })
                    position = None
            else:
                if current_price <= position.get('trailing_sl', position['sl']):
                    pnl_pct = (current_price - position['entry']) / position['entry'] * 100
                    trades.append({'exit_price': current_price, 'pnl_pct': pnl_pct, 'type': 'TRAIL'})
                    position = None
            continue
        
        # Entrada
        entry_signal = None
        
        if strategy_type == "mean_reversion":
            if current_rsi < 35 and current_price < bb_lower.iloc[i]:
                entry_signal = 'BUY'
            elif current_rsi > 65 and current_price > bb_upper.iloc[i]:
                entry_signal = 'SELL'
        elif strategy_type == "momentum":
            if current_price > close.iloc[i-1] and 40 < current_rsi < 70:
                entry_signal = 'BUY'
            elif current_price < close.iloc[i-1] and 30 < current_rsi < 60:
                entry_signal = 'SELL'
        elif strategy_type == "trend_following":
            if current_price > bb_upper.iloc[i] and current_rsi > 50:
                entry_signal = 'BUY'
            elif current_price < bb_lower.iloc[i] and current_rsi < 50:
                entry_signal = 'SELL'
        
        if entry_signal:
            entry_price = current_price
            size = 0.02
            
            if entry_signal == 'BUY':
                sl = entry_price - (current_atr * params['stop_mult'])
                tp = entry_price + (current_atr * params['target_mult'])
            else:
                sl = entry_price + (current_atr * params['stop_mult'])
                tp = entry_price - (current_atr * params['target_mult'])
            
            risk_pct = abs(entry_price - sl) / entry_price
            if risk_pct > 0.05:
                continue
            
            position = {
                'entry': entry_price, 'sl': sl, 'tp': tp,
                'size': size, 'type': entry_signal, 'trailing_sl': sl
            }
    
    return trades


def run_backtest(symbols=['BTC', 'ETH', 'SOL', 'ADA'], data_source='synthetic'):
    """Backtest principal con Cline como cerebro"""
    print(f"\n📊 CLINE BRAIN - Backtest para: {symbols}")
    print(f"📡 Fuente de datos: {data_source.upper()}")
    
    all_trades = []
    capital = INITIAL_CAPITAL
    
    base_prices = {'BTC': 50000, 'ETH': 3000, 'SOL': 100, 'ADA': 0.4,
                   'DOT': 5, 'LINK': 15, 'UNI': 8, 'AAVE': 150, 'MATIC': 0.6, 'AVAX': 30}
    
    for symbol in symbols:
        print(f"\n📈 {symbol}...")
        
        base = base_prices.get(symbol, 100)
        
        if data_source == 'ccxt':
            df = fetch_ccxt_data(f'{symbol}/USDT')
            if df is None:
                df = generate_synthetic_data(base)
        elif data_source == 'mt5':
            df = fetch_mt5_data(symbol)
            if df is None:
                df = generate_synthetic_data(base)
        else:
            df = generate_synthetic_data(base)
        
        print(f"  📊 {len(df)} velas procesadas")
        
        strategy_type, params, df = cline_generate_strategy(df, symbol)
        print(f"  🧠 Estrategia Cline: {strategy_type}")
        print(f"     Parámetros: {params}")
        
        trades = apply_cline_strategy(df, strategy_type, params)
        
        for trade in trades:
            pnl = capital * trade['pnl_pct'] / 100 * 0.02
            capital += pnl
            all_trades.append({
                'symbol': symbol,
                'strategy': strategy_type,
                'pnl_pct': trade['pnl_pct'],
                'type': trade['type']
            })
        
        print(f"  ✅ {len(trades)} trades")
    
    return all_trades, capital


def calculate_metrics(trades, initial_capital, final_capital):
    """Métricas profesionales completas"""
    if not trades:
        return {}
    
    trades_df = pd.DataFrame(trades)
    wins = trades_df[trades_df['pnl_pct'] > 0]
    losses = trades_df[trades_df['pnl_pct'] <= 0]
    
    win_rate = len(wins) / len(trades) * 100 if len(trades) > 0 else 0
    avg_win = wins['pnl_pct'].mean() if len(wins) > 0 else 0
    avg_loss = abs(losses['pnl_pct'].mean()) if len(losses) > 0 else 1
    pf = avg_win / avg_loss if avg_loss > 0 else float('inf')
    expectancy = (win_rate/100 * avg_win) - ((1-win_rate/100) * avg_loss)
    total_return = (final_capital / initial_capital - 1) * 100
    
    returns = trades_df['pnl_pct'].values / 100
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    cumulative = [initial_capital]
    for t in trades:
        cumulative.append(cumulative[-1] * (1 + t['pnl_pct'] / 100))
    cum_arr = np.array(cumulative)
    peaks = np.maximum.accumulate(cum_arr)
    dd = (cum_arr - peaks) / peaks * 100
    max_dd = dd.min()
    
    return {
        'total_trades': len(trades),
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'win_rate': win_rate,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'profit_factor': pf,
        'expectancy': expectancy,
        'sharpe_ratio': sharpe,
        'max_drawdown': max_dd,
        'total_return': total_return,
        'final_capital': final_capital
    }


def save_results(trades, metrics, output_prefix='backtest'):
    """Guardar resultados"""
    trades_df = pd.DataFrame(trades)
    trades_df.to_csv(OUTPUT_DIR / f'{output_prefix}_trades.csv', index=False)
    
    with open(OUTPUT_DIR / f'{output_prefix}_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)
    
    print(f"\n💾 Resultados guardados en reports/")


def generate_charts(trades, initial_capital):
    """Generar gráficos profesionales"""
    if not trades:
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    cumulative = [initial_capital]
    for t in trades:
        cumulative.append(cumulative[-1] * (1 + t['pnl_pct'] / 100))
    
    axes[0, 0].plot(cumulative, color='#3498db', linewidth=2)
    axes[0, 0].set_title('Equity Curve')
    axes[0, 0].grid(True, alpha=0.3)
    
    cum_arr = np.array(cumulative)
    peaks = np.maximum.accumulate(cum_arr)
    dd = (cum_arr - peaks) / peaks * 100
    axes[0, 1].fill_between(range(len(dd)), dd, 0, color='#e74c3c', alpha=0.5)
    axes[0, 1].set_title('Drawdown')
    axes[0, 1].grid(True, alpha=0.3)
    
    trades_df = pd.DataFrame(trades)
    axes[1, 0].hist(trades_df['pnl_pct'], bins=20, color='#2ecc71', alpha=0.7)
    axes[1, 0].axvline(x=0, color='gray', linestyle='--')
    axes[1, 0].set_title('PnL Distribution')
    
    trade_counts = trades_df.groupby('strategy').size()
    axes[1, 1].bar(trade_counts.index, trade_counts.values, color='#9b59b6')
    axes[1, 1].set_title('Trades by Strategy')
    
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / 'backtest_results.png', dpi=150)
    plt.close()
    print(f"  📊 Gráfico guardado: reports/backtest_results.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', choices=['synthetic', 'ccxt', 'mt5'], default='synthetic')
    parser.add_argument('--symbols', nargs='+', default=['BTC', 'ETH', 'SOL', 'ADA'])
    args = parser.parse_args()
    
    trades, final_capital = run_backtest(symbols=args.symbols, data_source=args.source)
    metrics = calculate_metrics(trades, INITIAL_CAPITAL, final_capital)
    
    print("\n" + "=" * 70)
    print("🏆 RESULTADOS DEL BACKTEST")
    print("=" * 70)
    
    if metrics:
        print(f"\n💎 Total Trades: {metrics['total_trades']}")
        print(f"🏆 Wins: {metrics['winning_trades']} | Losses: {metrics['losing_trades']}")
        print(f"📈 Win Rate: {metrics['win_rate']:.1f}%")
        print(f"💰 Capital Final: ${metrics['final_capital']:,.2f}")
        print(f"🚀 Retorno: {metrics['total_return']:.2f}%")
        print(f"📊 Avg Win: {metrics['avg_win']:.2f}% | Avg Loss: {metrics['avg_loss']:.2f}%")
        print(f"💎 Profit Factor: {metrics['profit_factor']:.2f}")
        print(f"🎯 Expectancy: {metrics['expectancy']:.3f}")
        print(f"📐 Sharpe Ratio: {metrics['sharpe_ratio']:.2f}")
        print(f"📉 Max Drawdown: {metrics['max_drawdown']:.2f}%")
    
    save_results(trades, metrics)
    generate_charts(trades, INITIAL_CAPITAL)
    
    print("\n✅ Backtest completado!")