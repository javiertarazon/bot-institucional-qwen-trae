"""
Métricas de Capacidad de Capital y Turnover
Calcula el tamaño máximo de capital y costes de transacción
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class CapacityTurnoverConfig:
    """Configuración para métricas de capacidad y turnover"""
    base_capital: float = 100000.0          # Capital base
    max_allowed_slippage_pct: float = 0.01  # Máximo slippage aceptable (1%)
    target_return_pct: float = 0.10         # Rendimiento objetivo anual
    rebalance_frequency_days: int = 21       # Frecuencia de rebalanceo (1 mes)
    liquidity_factor: float = 0.05           # Porcentaje de volumen diario que se puede negociar


class CapacityTurnoverAnalyzer:
    """Analizador de capacidad de capital y turnover"""
    
    def __init__(self, config: CapacityTurnoverConfig):
        self.config = config
        self.trades: List[Dict[str, Any]] = []
        self.results: Dict[str, Any] = {}
        
    def calculate_turnover(
        self,
        trades: List[Dict[str, Any]],
        initial_capital: float
    ) -> Dict[str, Any]:
        """
        Calcula métricas de turnover de la cartera
        """
        logger.info("Calculando métricas de turnover")
        
        if not trades:
            return {
                'total_turnover_pct': 0.0,
                'annualized_turnover_pct': 0.0,
                'total_transaction_costs': 0.0,
                'avg_position_holding_days': 0.0
            }
        
        # Calcular volumen total negociado
        total_volume = 0.0
        total_costs = 0.0
        
        for trade in trades:
            if trade['type'] == 'BUY':
                total_volume += trade['cost']
            elif trade['type'] == 'SELL':
                total_volume += trade.get('proceeds', 0)
            
            # Sumar comisiones y costes
            if 'cost' in trade:
                total_costs += trade['cost'] * 0.001  # 0.1% de comisión
            if 'proceeds' in trade:
                total_costs += trade['proceeds'] * 0.001
        
        # Turnover total (volumen / capital)
        total_turnover = total_volume / initial_capital
        
        # Calcular período de tiempo para anualizar
        if len(trades) >= 2:
            dates = [t['date'] for t in trades]
            start_date = min(dates)
            end_date = max(dates)
            
            days = (end_date - start_date).days if hasattr(end_date, '__sub__') else 365
            if days > 0:
                annualized_turnover = total_turnover * (365 / days)
            else:
                annualized_turnover = total_turnover
        else:
            annualized_turnover = total_turnover
        
        # Calcular tiempo medio de retención
        holding_times = []
        for i in range(len(trades)):
            if trades[i]['type'] == 'SELL':
                # Buscar la compra correspondiente
                for j in range(i-1, -1, -1):
                    if trades[j]['type'] == 'BUY' and trades[j].get('status') != 'closed':
                        if 'date' in trades[j] and 'date' in trades[i]:
                            delta = trades[i]['date'] - trades[j]['date']
                            holding_times.append(delta.days)
                        trades[j]['status'] = 'closed'
                        break
        
        avg_holding = np.mean(holding_times) if holding_times else 0.0
        
        return {
            'total_turnover_pct': total_turnover * 100,
            'annualized_turnover_pct': annualized_turnover * 100,
            'total_transaction_costs': total_costs,
            'transaction_costs_pct': (total_costs / initial_capital) * 100,
            'avg_position_holding_days': avg_holding
        }
    
    def estimate_market_impact(
        self,
        position_size: float,
        avg_daily_volume: float,
        volatility: float
    ) -> float:
        """
        Estima el impacto de mercado de una posición
        Usa una versión simplificada del modelo de Almgren-Chriss
        """
        # Porcentaje del volumen diario
        volume_pct = position_size / avg_daily_volume if avg_daily_volume > 0 else 0
        
        # Impacto de mercado (simplificado)
        # Impacto = 0.1 * (volumen_pct) * volatilidad
        impact = 0.1 * volume_pct * volatility
        
        return min(impact, 0.5)  # Máximo 50% de impacto
    
    def calculate_capacity(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        avg_daily_volume: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Calcula la capacidad máxima de capital de la estrategia
        """
        from .engine import BacktestEngine, BacktestConfig
        
        logger.info("Calculando capacidad de capital")
        
        # Estimar volumen si no se proporciona
        if avg_daily_volume is None:
            if 'Volume' in data.columns:
                avg_daily_volume = data['Volume'].mean()
            else:
                avg_daily_volume = 1000000.0  # Valor por defecto
        
        # Calcular volatilidad
        if 'Close' in data.columns:
            returns = data['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)
        else:
            volatility = 0.3  # 30% anual por defecto
        
        # Método de aproximación: probar diferentes tamaños de capital
        # y encontrar el máximo donde el impacto no reduce el rendimiento demasiado
        
        capital_levels = [100000, 500000, 1000000, 5000000, 10000000, 
                          50000000, 100000000, 500000000, 1000000000]
        
        capacity_results = []
        
        for capital in capital_levels:
            config = BacktestConfig(initial_capital=capital)
            engine = BacktestEngine(config)
            
            # Ejecutar backtest
            result = engine.run(data, strategy)
            
            # Estimar impacto de mercado
            # Suponemos que cada posición es ~10% del capital
            position_size = capital * 0.1
            market_impact = self.estimate_market_impact(
                position_size, avg_daily_volume, volatility
            )
            
            # Rendimiento neto (después de impacto)
            net_return = result['total_return'] - market_impact
            
            capacity_results.append({
                'capital': capital,
                'gross_return': result['total_return'],
                'market_impact_pct': market_impact * 100,
                'net_return': net_return,
                'sharpe_ratio': result['sharpe_ratio']
            })
            
            # Detener si el impacto es mayor que el rendimiento
            if market_impact > result['total_return'] or market_impact > self.config.max_allowed_slippage_pct:
                break
        
        # Encontrar el capital máximo donde el rendimiento neto es positivo
        max_capacity = self.config.base_capital
        for res in capacity_results:
            if (res['net_return'] > 0 and 
                res['market_impact_pct'] < self.config.max_allowed_slippage_pct * 100):
                max_capacity = res['capital']
        
        return {
            'max_capacity': max_capacity,
            'capacity_levels': capacity_results,
            'estimated_volatility': volatility,
            'avg_daily_volume': avg_daily_volume
        }
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        avg_daily_volume: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Ejecuta el análisis completo de capacidad y turnover
        """
        from .engine import BacktestEngine, BacktestConfig
        
        logger.info("Iniciando análisis de capacidad y turnover")
        
        # Ejecutar backtest para obtener trades
        backtest_config = BacktestConfig(initial_capital=self.config.base_capital)
        engine = BacktestEngine(backtest_config)
        backtest_result = engine.run(data, strategy)
        
        # Obtener trades del engine (adaptamos la estructura)
        self.trades = engine.trades
        
        # Calcular turnover
        turnover_metrics = self.calculate_turnover(self.trades, self.config.base_capital)
        
        # Calcular capacidad
        capacity_metrics = self.calculate_capacity(data, strategy, avg_daily_volume)
        
        # Verificar umbrales
        passes_turnover_threshold = turnover_metrics['annualized_turnover_pct'] < 200  # Menos de 2x anual
        passes_capacity_threshold = capacity_metrics['max_capacity'] >= 1000000  # Al menos $1M
        
        self.results = {
            'turnover_metrics': turnover_metrics,
            'capacity_metrics': capacity_metrics,
            'backtest_result': backtest_result,
            'summary': {
                'passes_turnover_threshold': passes_turnover_threshold,
                'passes_capacity_threshold': passes_capacity_threshold,
                'overall_viable': passes_turnover_threshold and passes_capacity_threshold
            }
        }
        
        logger.info("Análisis de capacidad y turnover completado")
        return self.results
    
    def export_report(self, filepath):
        """Exporta el reporte"""
        if not self.results:
            logger.warning("No hay resultados para exportar")
            return
        
        # Convertir Path a string si es necesario
        filepath_str = str(filepath)
        
        # Exportar métricas de turnover
        turnover_df = pd.DataFrame([{
            'metric': k,
            'value': v
        } for k, v in self.results['turnover_metrics'].items()])
        turnover_df.to_csv(filepath_str.replace('.csv', '_turnover.csv'), index=False)
        
        # Exportar niveles de capacidad
        capacity_df = pd.DataFrame(self.results['capacity_metrics']['capacity_levels'])
        capacity_df.to_csv(filepath_str.replace('.csv', '_capacity.csv'), index=False)
        
        logger.info(f"Reporte exportado a {filepath}")
