#!/usr/bin/env python3
"""
🚀 BACKTEST OPTIMIZADO v4.0 - CLINE BRAIN MEJORADO
Pruebas con las 4 mejoras implementadas:
1. Estrategia Breakout como tercer voto
2. Optimización walk-forward de parámetros
3. Predictor ONNX (o fallback estadístico)
4. Sentimiento como factor generador de señales

Incluye tests con datos reales de CCXT cuando está disponible.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings('ignore')
from datetime import datetime, timedelta
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Importar cerebro optimizado
sys.path.insert(0, str(Path(__file__).parent / '09_brain_cline'))
from brain_optimized import ClineBrainOptimized

print("=" * 80)
print("🧠 BACKTEST CLINE BRAIN v4.0 OPTIMIZADO")
print("=" * 80)


def fetch_real_data(symbol='BTC/USDT', timeframe='1h', days=90):
    """
    Obtiene datos reales de CCXT (Binance).
    Fallback a datos sintéticos si no hay conexión.
    """
    try:
        import ccxt
        print(f"\n📡 Conectando a Binance para obtener datos reales de {symbol}...")
        
        exchange = ccxt.binance()
        exchange.enableRateLimit = True
        
        since = exchange.parse8601((datetime.now() - timedelta(days=days)).isoformat())
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=5000)
        
        if len(ohlcv) == 0:
            print(f"⚠️ No se obtuvieron datos de {symbol}")
            return None, "synthetic"
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        print(f"✅ Datos reales obtenidos: {len(df)} velas desde {df.index[0]} hasta {df.index[-1]}")
        return df, "real"
    
    except Exception as e:
        print(f"⚠️ CCXT no disponible: {e}")
        print("🔄 Usando datos sintéticos como fallback")
        return None, "synthetic"


def generate_synthetic_data(base_price=50000, n=2000, trend='mixed'):
    """
    Genera datos sintéticos realistas con diferentes regímenes.
    """
    np.random.seed(42)
    
    prices = [base_price]
    
    for i in range(n-1):
        # Régimen cambiante
        regime_phase = (i // 200) % 5
        
        if regime_phase == 0:  # Tendencia alcista
            drift = 0.002
            vol = 0.015
        elif regime_phase == 1:  # Tendencia bajista
            drift = -0.002
            vol = 0.02
        elif regime_phase == 2:  # Lateral
            drift = 0.0
            vol = 0.01
        elif regime_phase == 3:  # Volátil
            drift = 0.001
            vol = 0.035
        else:  # Momentum fuerte
            drift = 0.003 if i % 100 < 50 else -0.003
            vol = 0.025
        
        ret = np.random.normal(drift, vol)
        
        # Eventos extremos ocasionales
        if np.random.random() < 0.02:
            ret += np.random.uniform(-0.05, 0.05)
        
        new_price = prices[-1] * (1 + ret)
        new_price = max(new_price, base_price * 0.3)  # Floor
        new_price = min(new_price, base_price * 3.0)  # Cap
        
        prices.append(new_price)
    
    # Crear DataFrame
    prices = np.array(prices)
    df = pd.DataFrame({
        'close': prices,
        'high': prices * (1 + np.abs(np.random.normal(0.005, 0.005, n))),
        'low': prices * (1 - np.abs(np.random.normal(0.005, 0.005, n))),
        'volume': np.random.randint(10000, 500000, n) * (prices / base_price)
    })
    
    # Asegurar coherencia OHLC
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    return df


class BacktesterV4:
    """
    Backtester profesional para Cline Brain v4.0
    """
    
    def __init__(self, initial_capital=10000.0, commission=0.001):
        self.initial_capital = initial_capital
        self.commission = commission
        self.brain = None
    
    def run_backtest(self, df: pd.DataFrame, symbol: str = 'BTC/USDT',
                     use_real_sentiment: bool = False) -> dict:
        """
        Ejecuta backtest completo con cerebro optimizado.
        """
        print(f"\n{'='*80}")
        print(f"📊 EJECUTANDO BACKTEST EN {symbol}")
        print(f"{'='*80}")
        print(f"Período: {df.index[0]} a {df.index[-1]}")
        print(f"Total velas: {len(df)}")
        print(f"Capital inicial: ${self.initial_capital:,.2f}")
        
        # Inicializar cerebro
        self.brain = ClineBrainOptimized(config={
            'breakout_lookback': 20,
            'volume_threshold': 1.5,
            'wf_window': 100,
            'wf_step': 20
        })
        
        # Variables de tracking
        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = [capital]
        signals_history = []
        
        # Warmup para indicadores
        warmup_period = 100
        
        print(f"\n🔄 Procesando {len(df) - warmup_period} señales...")
        
        for i in range(warmup_period, len(df)):
            # Datos hasta el momento
            data_slice = df.iloc[:i+1].copy()
            
            # Simular sentimiento externo (opcional)
            external_sentiment = None
            if use_real_sentiment:
                # Simular Fear & Greed Index basado en momentum reciente
                returns_7 = data_slice['close'].pct_change(7).iloc[-1]
                fng = int(50 + returns_7 * 500)  # Mapear a 0-100
                fng = max(0, min(100, fng))
                external_sentiment = {'fear_greed_index': fng}
            
            # Obtener decisión del cerebro
            decision = self.brain.analyze_and_decide(
                df=data_slice,
                symbol=symbol,
                external_sentiment=external_sentiment
            )
            
            current_price = data_slice['close'].iloc[-1]
            timestamp = data_slice.index[-1]
            
            # Gestionar posición abierta
            if position:
                # Check stop loss o take profit
                if position['type'] == 'BUY':
                    if current_price <= position['sl']:
                        # Stop loss hit
                        pnl_pct = (position['sl'] - position['entry']) / position['entry'] * 100
                        exit_reason = 'SL'
                    elif current_price >= position['tp']:
                        # Take profit hit
                        pnl_pct = (position['tp'] - position['entry']) / position['entry'] * 100
                        exit_reason = 'TP'
                    else:
                        pnl_pct = None
                else:  # SELL
                    if current_price >= position['sl']:
                        pnl_pct = (position['entry'] - position['sl']) / position['entry'] * 100
                        exit_reason = 'SL'
                    elif current_price <= position['tp']:
                        pnl_pct = (position['entry'] - position['tp']) / position['entry'] * 100
                        exit_reason = 'TP'
                    else:
                        pnl_pct = None
                
                # Si hay salida
                if pnl_pct is not None:
                    # Aplicar comisión
                    pnl_net = pnl_pct * (1 - self.commission * 2)
                    
                    # Actualar capital
                    capital *= (1 + pnl_net / 100)
                    
                    # Registrar trade
                    trades.append({
                        'timestamp': timestamp,
                        'entry': position['entry'],
                        'exit': position['sl'] if exit_reason == 'SL' else position['tp'],
                        'type': position['type'],
                        'pnl_pct': pnl_pct,
                        'pnl_net': pnl_net,
                        'exit_reason': exit_reason,
                        'capital': capital
                    })
                    
                    # Actualar peso de breakout strategy
                    if position['strategy'] == 'breakout':
                        self.brain.breakout_strategy.record_trade_result(pnl_net / 100)
                    
                    position = None
            
            # Entrar en nueva posición si hay señal y no hay posición
            if position is None and decision['signal'] in ['BUY', 'SELL']:
                confidence = decision['confidence']
                
                # Filter por confianza mínima
                if confidence > 0.45:
                    signal_type = decision['signal']
                    entry_price = current_price
                    sl = decision['stop_loss']
                    tp = decision['take_profit']
                    
                    # Validar R:R mínimo
                    if signal_type == 'BUY':
                        risk = (entry_price - sl) / entry_price
                        reward = (tp - entry_price) / entry_price
                    else:
                        risk = (sl - entry_price) / entry_price
                        reward = (entry_price - tp) / entry_price
                    
                    rr = reward / risk if risk > 0 else 0
                    
                    if rr >= 1.5:  # Mínimo 1.5:1
                        # Calcular tamaño de posición
                        risk_per_trade = 0.02  # 2% del capital
                        position_size = (capital * risk_per_trade) / (entry_price - sl if signal_type == 'BUY' else sl - entry_price)
                        
                        position = {
                            'type': signal_type,
                            'entry': entry_price,
                            'sl': sl,
                            'tp': tp,
                            'size': position_size,
                            'timestamp': timestamp,
                            'rr': rr,
                            'strategy': self._detect_dominant_strategy(decision['votes'])
                        }
            
            # Tracking
            equity_curve.append(capital)
            signals_history.append({
                'timestamp': timestamp,
                'signal': decision['signal'],
                'confidence': decision['confidence'],
                'regime': decision['market_regime'],
                'in_position': position is not None
            })
        
        # Cerrar posición final si existe
        if position:
            final_price = df['close'].iloc[-1]
            if position['type'] == 'BUY':
                pnl_pct = (final_price - position['entry']) / position['entry'] * 100
            else:
                pnl_pct = (position['entry'] - final_price) / position['entry'] * 100
            
            pnl_net = pnl_pct * (1 - self.commission * 2)
            capital *= (1 + pnl_net / 100)
            
            trades.append({
                'timestamp': df.index[-1],
                'entry': position['entry'],
                'exit': final_price,
                'type': position['type'],
                'pnl_pct': pnl_pct,
                'pnl_net': pnl_net,
                'exit_reason': 'CLOSE',
                'capital': capital
            })
        
        # Calcular métricas
        metrics = self._calculate_metrics(trades, equity_curve, df)
        
        # Guardar resultados
        results = {
            'trades': trades,
            'equity_curve': equity_curve,
            'signals_history': signals_history,
            'metrics': metrics,
            'symbol': symbol,
            'period': f"{df.index[0]} to {df.index[-1]}",
            'data_source': 'real' if len(df) > 1000 and abs(df['close'].iloc[-1] - 50000) > 10000 else 'synthetic'
        }
        
        return results
    
    def _detect_dominant_strategy(self, votes: list) -> str:
        """Detecta qué estrategia dominó la decisión"""
        if not votes:
            return 'unknown'
        
        # Buscar voto con mayor peso * confianza
        best_vote = max(votes, key=lambda v: v[2] * v[3])
        return best_vote[0]
    
    def _calculate_metrics(self, trades: list, equity_curve: list, df: pd.DataFrame) -> dict:
        """Calcula métricas de performance completas"""
        if not trades:
            return {'error': 'No trades executed'}
        
        # Métricas básicas
        total_trades = len(trades)
        winning_trades = sum(1 for t in trades if t['pnl_net'] > 0)
        losing_trades = sum(1 for t in trades if t['pnl_net'] <= 0)
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        # Retornos
        total_return = (equity_curve[-1] / self.initial_capital - 1) * 100
        
        # Drawdown
        peak = equity_curve[0]
        max_drawdown = 0
        drawdowns = []
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            drawdowns.append(drawdown)
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # Profit Factor
        gross_profit = sum(t['pnl_net'] for t in trades if t['pnl_net'] > 0)
        gross_loss = abs(sum(t['pnl_net'] for t in trades if t['pnl_net'] < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Sharpe Ratio (aproximado)
        returns = np.diff(equity_curve) / equity_curve[:-1]
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        
        # Calmar Ratio
        annualized_return = total_return / (len(df) / 8760)  # Horas a años
        calmar = annualized_return / max_drawdown if max_drawdown > 0 else 0
        
        # Average R:R
        avg_rr = np.mean([t.get('rr', 0) for t in trades if t.get('rr', 0) > 0])
        
        # Expectancy
        avg_win = np.mean([t['pnl_net'] for t in trades if t['pnl_net'] > 0]) if winning_trades > 0 else 0
        avg_loss = np.mean([t['pnl_net'] for t in trades if t['pnl_net'] < 0]) if losing_trades > 0 else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss))
        
        # Strategy breakdown
        strategy_stats = {}
        strategies = set(t.get('strategy', 'unknown') for t in trades)
        for strat in strategies:
            strat_trades = [t for t in trades if t.get('strategy') == strat]
            if strat_trades:
                strat_wins = sum(1 for t in strat_trades if t['pnl_net'] > 0)
                strategy_stats[strat] = {
                    'trades': len(strat_trades),
                    'wins': strat_wins,
                    'win_rate': strat_wins / len(strat_trades),
                    'total_pnl': sum(t['pnl_net'] for t in strat_trades)
                }
        
        metrics = {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'total_return_pct': total_return,
            'final_capital': equity_curve[-1],
            'max_drawdown_pct': max_drawdown,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'calmar_ratio': calmar,
            'avg_rr': avg_rr,
            'expectancy': expectancy,
            'avg_win_pct': avg_win,
            'avg_loss_pct': avg_loss,
            'strategy_breakdown': strategy_stats,
            'largest_win': max(t['pnl_net'] for t in trades),
            'largest_loss': min(t['pnl_net'] for t in trades),
            'consecutive_wins': self._max_consecutive(trades, True),
            'consecutive_losses': self._max_consecutive(trades, False)
        }
        
        return metrics
    
    def _max_consecutive(self, trades: list, wins: bool) -> int:
        """Calcula máxima racha de victorias/derrotas"""
        max_consec = 0
        current_consec = 0
        
        for t in trades:
            is_win = t['pnl_net'] > 0
            if is_win == wins:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                current_consec = 0
        
        return max_consec
    
    def plot_results(self, results: dict, save_path: str = None):
        """Genera gráficos de resultados"""
        trades = results['trades']
        equity_curve = results['equity_curve']
        metrics = results['metrics']
        
        if not trades:
            print("⚠️ No hay trades para graficar")
            return
        
        fig, axes = plt.subplots(3, 1, figsize=(14, 10))
        
        # 1. Equity Curve
        ax1 = axes[0]
        ax1.plot(equity_curve, linewidth=2, label='Equity')
        ax1.axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.5, label='Initial Capital')
        ax1.set_title(f"Equity Curve - {results['symbol']} ({results['data_source']})")
        ax1.set_ylabel('Capital ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # 2. Drawdown
        ax2 = axes[1]
        peak = equity_curve[0]
        drawdowns = []
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak * 100
            drawdowns.append(drawdown)
        
        ax2.fill_between(range(len(drawdowns)), 0, drawdowns, alpha=0.7, color='red')
        ax2.set_title('Drawdown')
        ax2.set_ylabel('Drawdown (%)')
        ax2.grid(True, alpha=0.3)
        
        # 3. Trade Distribution
        ax3 = axes[2]
        pnls = [t['pnl_net'] for t in trades]
        colors = ['green' if p > 0 else 'red' for p in pnls]
        ax3.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        ax3.set_title(f'Trade P&L Distribution (Total: {len(trades)} trades)')
        ax3.set_ylabel('P&L (%)')
        ax3.set_xlabel('Trade #')
        ax3.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"📊 Gráfico guardado en: {save_path}")
        else:
            plt.show()


def main():
    """Función principal de backtest"""
    
    # Configuración
    SYMBOLS_TO_TEST = ['BTC/USDT']
    DAYS_OF_DATA = 90
    INITIAL_CAPITAL = 10000.0
    
    # Fetch datos (reales o sintéticos)
    all_results = []
    
    for symbol in SYMBOLS_TO_TEST:
        df, data_source = fetch_real_data(symbol, timeframe='1h', days=DAYS_OF_DATA)
        
        if df is None:
            # Generar datos sintéticos
            print(f"\n📊 Generando datos sintéticos para {symbol}...")
            df = generate_synthetic_data(base_price=50000, n=2000, trend='mixed')
            data_source = 'synthetic'
        
        # Ejecutar backtest
        backtester = BacktesterV4(initial_capital=INITIAL_CAPITAL)
        results = backtester.run_backtest(df, symbol, use_real_sentiment=True)
        
        # Imprimir métricas
        metrics = results['metrics']
        
        print("\n" + "=" * 80)
        print(f"📈 RESULTADOS DEL BACKTEST - {symbol}")
        print(f"Fuente de datos: {data_source.upper()}")
        print("=" * 80)
        
        print(f"\n💰 MÉTRICAS DE RENTABILIDAD:")
        print(f"  Capital Final:      ${metrics['final_capital']:,.2f}")
        print(f"  Retorno Total:      {metrics['total_return_pct']:+.2f}%")
        print(f"  Win Rate:           {metrics['win_rate']*100:.1f}% ({metrics['winning_trades']}/{metrics['total_trades']})")
        print(f"  Profit Factor:      {metrics['profit_factor']:.2f}")
        
        print(f"\n📊 MÉTRICAS DE RIESGO:")
        print(f"  Max Drawdown:       {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Sharpe Ratio:       {metrics['sharpe_ratio']:.2f}")
        print(f"  Calmar Ratio:       {metrics['calmar_ratio']:.2f}")
        print(f"  Avg R:R:            {metrics['avg_rr']:.2f}:1")
        
        print(f"\n🎯 EXPECTATIVA Y RACHAS:")
        print(f"  Expectancy:         {metrics['expectancy']:.2f}%")
        print(f"  Mayor Ganancia:     {metrics['largest_win']:+.2f}%")
        print(f"  Mayor Pérdida:      {metrics['largest_loss']:+.2f}%")
        print(f"  Rachas Máx:         {metrics['consecutive_wins']} wins / {metrics['consecutive_losses']} losses")
        
        if 'strategy_breakdown' in metrics and metrics['strategy_breakdown']:
            print(f"\n🧠 PERFORMANCE POR ESTRATEGIA:")
            for strat, stats in metrics['strategy_breakdown'].items():
                print(f"  {strat}:")
                print(f"    Trades: {stats['trades']}, Win Rate: {stats['win_rate']*100:.1f}%, P&L: {stats['total_pnl']:+.2f}%")
        
        print("=" * 80)
        
        # Guardar resultados
        all_results.append(results)
        
        # Generar gráfico
        output_dir = Path(__file__).parent / 'reports'
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        chart_path = output_dir / f'backtest_v4_{symbol.replace("/", "_")}_{timestamp}.png'
        backtester.plot_results(results, save_path=str(chart_path))
    
    # Resumen comparativo si hay múltiples resultados
    if len(all_results) > 1:
        print("\n\n" + "=" * 80)
        print("📋 RESUMEN COMPARATIVO")
        print("=" * 80)
        print(f"{'Símbolo':<15} {'Retorno':<12} {'Win Rate':<12} {'Profit Factor':<15} {'Sharpe':<10} {'Drawdown':<12}")
        print("-" * 80)
        
        for results in all_results:
            m = results['metrics']
            print(f"{results['symbol']:<15} {m['total_return_pct']:>+11.2f}% {m['win_rate']*100:>11.1f}% {m['profit_factor']:>14.2f} {m['sharpe_ratio']:>9.2f} {m['max_drawdown_pct']:>11.2f}%")
        
        print("=" * 80)
    
    # Guardar resultados en JSON
    output_dir = Path(__file__).parent / 'reports'
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = output_dir / f'backtest_v4_results_{timestamp}.json'
    
    # Convertir para JSON serialization
    json_results = []
    for r in all_results:
        r_copy = r.copy()
        r_copy['equity_curve'] = r['equity_curve'][-100:]  # Últimos 100 puntos
        json_results.append(r_copy)
    
    with open(json_path, 'w') as f:
        json.dump(json_results, f, indent=2, default=str)
    
    print(f"\n💾 Resultados guardados en: {json_path}")
    print("\n✅ Backtest completado exitosamente!")
    
    return all_results


if __name__ == "__main__":
    results = main()
