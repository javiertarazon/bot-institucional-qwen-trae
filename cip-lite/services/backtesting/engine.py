"""
Módulo de Backtesting Profesional para CIP
Incluye: Datos históricos, engine, métricas y visualización
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
import structlog
import warnings
warnings.filterwarnings("ignore")

logger = structlog.get_logger()


@dataclass
class BacktestConfig:
    """Configuración del backtesting con parámetros realistas"""
    initial_capital: float = 100000.0
    commission_rate: float = 0.001  # 0.1% por operación
    slippage_pct: float = 0.0005    # 0.05% de deslizamiento
    max_position_pct: float = 0.1   # 10% máximo por posición
    risk_per_trade_pct: float = 0.02  # 2% de riesgo por operación
    lookback_window: int = 60       # Ventana de datos históricos para features


class HistoricalData:
    """Generador de datos históricos realistas (o integración con yfinance)"""
    @staticmethod
    def generate_synthetic_crypto_data(start_date: str, end_date: str, base_price: float = 50000.0, volatility: float = 0.02) -> pd.DataFrame:
        """Genera datos históricos sintéticos con tendencias, volatilidad y cycles"""
        logger.info("Generando datos históricos sintéticos")
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        n = len(dates)
        
        # Precios base con volatilidad
        np.random.seed(42)
        returns = np.random.normal(0, volatility, n)
        prices = base_price * np.cumprod(1 + returns)
        
        # Añadir tendencia
        trend = np.linspace(0, 0.5, n)
        prices = prices * (1 + trend)
        
        # Añadir ciclos
        cycle = 0.1 * np.sin(np.linspace(0, 20 * np.pi, n))
        prices = prices * (1 + cycle)
        
        # Añadir periodos de alta volatilidad
        volatility_periods = np.random.choice([0, 1], n, p=[0.9, 0.1])
        prices[volatility_periods == 1] = prices[volatility_periods == 1] * (1 + np.random.normal(0, 0.05, sum(volatility_periods)))
        
        df = pd.DataFrame({
            'Date': dates,
            'Open': prices * (1 - np.random.uniform(0, 0.01, n)),
            'High': prices * (1 + np.random.uniform(0, 0.03, n)),
            'Low': prices * (1 - np.random.uniform(0, 0.03, n)),
            'Close': prices,
            'Volume': np.random.randint(10000, 100000, n)
        })
        df.set_index('Date', inplace=True)
        
        logger.info(f"Datos generados: {n} días, desde {start_date} hasta {end_date}")
        return df


class BacktestEngine:
    """Motor de backtesting sin look-ahead bias"""
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.equity_curve: List[float] = []
        self.trades: List[Dict[str, Any]] = []
        self.current_position: Optional[Dict] = None
        self.position_entries: List[Dict] = []  # Para calcular tiempo de retención

    def run(self, data: pd.DataFrame, strategy) -> Dict[str, Any]:
        """Ejecuta el backtesting"""
        logger.info("Iniciando backtesting")
        self.equity_curve = [self.config.initial_capital]
        
        for idx in range(self.config.lookback_window, len(data)):
            current_date = data.index[idx]
            current_price = data['Close'].iloc[idx]
            
            # Obtener datos históricos hasta el momento (sin look-ahead)
            historical_data = data.iloc[:idx+1].copy()
            
            # Generar señal
            signal = strategy(historical_data)
            
            # Ejecutar operación
            self._execute_trade(signal, current_date, current_price)
            
            # Actualizar equity
            equity = self._calculate_current_equity(current_price)
            self.equity_curve.append(equity)
        
        results = self._calculate_results()
        logger.info("Backtesting completado")
        return results

    def _execute_trade(self, signal: str, date: datetime, price: float):
        """Ejecuta una operación con costos y slippage"""
        if signal == 'HOLD':
            return

        if signal == 'BUY' and not self.current_position:
            # Abrir posición
            position_size = min(
                self.config.initial_capital * self.config.max_position_pct,
                self.config.initial_capital * self.config.risk_per_trade_pct
            )
            shares = position_size / price
            # Aplicar slippage
            buy_price = price * (1 + self.config.slippage_pct)
            cost = shares * buy_price
            commission = cost * self.config.commission_rate

            self.current_position = {
                'entry_date': date,
                'entry_price': buy_price,
                'shares': shares,
                'entry_cost': cost + commission
            }
            # Guardar entrada para tiempo de retención
            self.position_entries.append({
                'entry_date': date,
                'status': 'open'
            })
            self.trades.append({
                'type': 'BUY',
                'date': date,
                'price': buy_price,
                'shares': shares,
                'cost': cost + commission
            })
            logger.debug(f"Compra ejecutada: {shares:.2f} @ {buy_price:.2f}")

        elif signal == 'SELL' and self.current_position:
            # Cerrar posición
            sell_price = price * (1 - self.config.slippage_pct)
            proceeds = self.current_position['shares'] * sell_price
            commission = proceeds * self.config.commission_rate
            net_proceeds = proceeds - commission

            pnl = net_proceeds - self.current_position['entry_cost']
            self.trades.append({
                'type': 'SELL',
                'date': date,
                'price': sell_price,
                'shares': self.current_position['shares'],
                'proceeds': net_proceeds,
                'pnl': pnl
            })
            # Actualizar la última posición abierta
            if self.position_entries:
                for entry in reversed(self.position_entries):
                    if entry['status'] == 'open':
                        entry['exit_date'] = date
                        entry['status'] = 'closed'
                        break
            logger.debug(f"Venta ejecutada: PnL {pnl:.2f}")
            self.current_position = None

    def _calculate_current_equity(self, current_price: float) -> float:
        """Calcula el equity actual"""
        equity = self.config.initial_capital
        for trade in self.trades:
            if trade['type'] == 'BUY':
                equity -= trade['cost']
            elif trade['type'] == 'SELL':
                equity += trade['proceeds']
        
        if self.current_position:
            position_value = self.current_position['shares'] * current_price
            equity += position_value
        
        return equity

    def _calculate_results(self) -> Dict[str, Any]:
        """Calcula métricas de rendimiento"""
        equity_series = pd.Series(self.equity_curve)
        returns = equity_series.pct_change().dropna()

        # Tasa de aciertos
        winning_trades = [t for t in self.trades if t['type'] == 'SELL' and t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['type'] == 'SELL' and t['pnl'] <= 0]
        win_rate = len(winning_trades) / (len(winning_trades) + len(losing_trades)) if (len(winning_trades) + len(losing_trades)) > 0 else 0

        # Rendimiento total y anualizado
        total_return = (self.equity_curve[-1] - self.equity_curve[0]) / self.equity_curve[0]
        n_years = len(returns) / 252  # Asumiendo 252 días/años
        annualized_return = (1 + total_return) ** (1 / n_years) - 1 if n_years > 0 else 0

        # Sharpe y Sortino ratios
        risk_free_rate = 0.03
        excess_returns = returns - risk_free_rate / 252
        sharpe_ratio = np.sqrt(252) * excess_returns.mean() / excess_returns.std() if (len(excess_returns) > 0 and excess_returns.std() != 0) else 0

        downside_returns = returns[returns < 0]
        sortino_ratio = np.sqrt(252) * excess_returns.mean() / downside_returns.std() if (downside_returns.std() != 0 and len(downside_returns) > 0) else 0

        # Max Drawdown
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.cummax()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min() if len(drawdown) > 0 else 0

        # Ratio de ganancia/pérdida promedio
        avg_win = np.mean([t['pnl'] for t in winning_trades]) if len(winning_trades) > 0 else 0
        avg_loss = abs(np.mean([t['pnl'] for t in losing_trades])) if len(losing_trades) > 0 else 1
        profit_loss_ratio = avg_win / avg_loss if avg_loss != 0 else 0

        # Tiempo medio de retención de posiciones (en días)
        holding_times = []
        for entry in self.position_entries:
            if entry['status'] == 'closed' and 'exit_date' in entry:
                delta = entry['exit_date'] - entry['entry_date']
                holding_times.append(delta.days)
        
        avg_holding_time = np.mean(holding_times) if len(holding_times) > 0 else 0

        return {
            'equity_curve': self.equity_curve,
            'total_trades': len([t for t in self.trades if t['type'] == 'SELL']),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'total_return': total_return,
            'annualized_return': annualized_return,
            'sharpe_ratio': sharpe_ratio,
            'sortino_ratio': sortino_ratio,
            'max_drawdown': max_drawdown,
            'profit_loss_ratio': profit_loss_ratio,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'avg_holding_time_days': avg_holding_time,
            'holding_times': holding_times
        }


class Strategy:
    """Estrategia basada en nuestro predictor ML + sistema de agentes"""
    @staticmethod
    def simple_trend_strategy(data: pd.DataFrame) -> str:
        """Estrategia simple de cruce de medias para demo"""
        if len(data) < 20:
            return 'HOLD'
        
        # Calcular medias móviles
        ma7 = data['Close'].tail(7).mean()
        ma21 = data['Close'].tail(21).mean()
        
        if ma7 > ma21 and ma7 > data['Close'].iloc[-1]:
            return 'BUY'
        elif ma7 < ma21:
            return 'SELL'
        else:
            return 'HOLD'
