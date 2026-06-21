"""
Módulo de Walk-Forward Analysis Institucional
Permite reentrenar modelos en ventanas móviles y evaluar rendimiento robusto
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import structlog
from datetime import datetime
from .engine import BacktestEngine, BacktestConfig

logger = structlog.get_logger()


@dataclass
class WalkForwardConfig:
    """Configuración para Walk-Forward Analysis"""
    train_window_days: int = 252        # Ventana de entrenamiento: 1 año
    test_window_days: int = 63          # Ventana de prueba: 3 meses
    step_days: int = 21                 # Paso: 1 mes
    initial_capital: float = 100000.0
    commission_rate: float = 0.001
    slippage_pct: float = 0.0005
    max_position_pct: float = 0.1


class WalkForwardAnalysis:
    """Motor de Walk-Forward Analysis"""
    
    def __init__(self, config: WalkForwardConfig):
        self.config = config
        self.windows: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        
    def generate_windows(self, data: pd.DataFrame) -> List[Dict[str, Any]]:
        """Genera las ventanas de entrenamiento y prueba"""
        logger.info("Generando ventanas para Walk-Forward Analysis")
        
        windows = []
        total_days = len(data)
        train_size = self.config.train_window_days
        test_size = self.config.test_window_days
        step = self.config.step_days
        
        idx = 0
        while idx + train_size + test_size <= total_days:
            train_start = idx
            train_end = idx + train_size
            test_start = train_end
            test_end = train_end + test_size
            
            windows.append({
                'window_id': len(windows),
                'train_start_idx': train_start,
                'train_end_idx': train_end,
                'test_start_idx': test_start,
                'test_end_idx': test_end,
                'train_start_date': data.index[train_start],
                'train_end_date': data.index[train_end - 1],
                'test_start_date': data.index[test_start],
                'test_end_date': data.index[test_end - 1]
            })
            
            idx += step
        
        self.windows = windows
        logger.info(f"Generadas {len(windows)} ventanas")
        return windows
    
    def run_window(
        self, 
        window: Dict[str, Any], 
        data: pd.DataFrame, 
        strategy: Callable,
        train_strategy_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Ejecuta una ventana individual"""
        logger.info(f"Ejecutando ventana {window['window_id']}")
        
        # Obtener datos de entrenamiento y prueba
        train_data = data.iloc[window['train_start_idx']:window['train_end_idx']].copy()
        test_data = data.iloc[window['test_start_idx']:window['test_end_idx']].copy()
        
        # Reentrenar la estrategia si se proporciona la función
        trained_strategy = strategy
        if train_strategy_func:
            trained_strategy = train_strategy_func(train_data)
        
        # Configurar backtesting
        backtest_config = BacktestConfig(
            initial_capital=self.config.initial_capital,
            commission_rate=self.config.commission_rate,
            slippage_pct=self.config.slippage_pct,
            max_position_pct=self.config.max_position_pct
        )
        
        # Ejecutar backtesting en ventana de prueba
        engine = BacktestEngine(backtest_config)
        result = engine.run(test_data, trained_strategy)
        
        # Añadir metadatos de la ventana
        result.update({
            'window_id': window['window_id'],
            'train_start_date': window['train_start_date'],
            'train_end_date': window['train_end_date'],
            'test_start_date': window['test_start_date'],
            'test_end_date': window['test_end_date']
        })
        
        return result
    
    def run(
        self, 
        data: pd.DataFrame, 
        strategy: Callable,
        train_strategy_func: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Ejecuta el Walk-Forward Analysis completo"""
        logger.info("Iniciando Walk-Forward Analysis")
        
        # Generar ventanas
        self.generate_windows(data)
        
        # Ejecutar cada ventana
        self.results = []
        for window in self.windows:
            result = self.run_window(window, data, strategy, train_strategy_func)
            self.results.append(result)
        
        # Generar reporte consolidado
        consolidated_report = self._generate_consolidated_report()
        
        logger.info("Walk-Forward Analysis completado")
        return consolidated_report
    
    def _generate_consolidated_report(self) -> Dict[str, Any]:
        """Genera reporte consolidado de todas las ventanas"""
        if not self.results:
            return {}
        
        # Extraer métricas clave
        total_returns = [r['total_return'] for r in self.results]
        sharpe_ratios = [r['sharpe_ratio'] for r in self.results]
        max_drawdowns = [r['max_drawdown'] for r in self.results]
        win_rates = [r['win_rate'] for r in self.results]
        
        # Calcular rendimiento acumulado
        cumulative_equity = []
        current_equity = self.config.initial_capital
        
        for result in self.results:
            # Calcular equity final de la ventana
            window_equity = current_equity * (1 + result['total_return'])
            cumulative_equity.append(window_equity)
            current_equity = window_equity
        
        # Calcular métricas de estabilidad
        return_std = np.std(total_returns)
        return_mean = np.mean(total_returns)
        stability_ratio = return_mean / return_std if return_std != 0 else 0
        
        # Calcular máximo drawdown acumulado
        cumulative_series = pd.Series(cumulative_equity)
        cumulative_returns = cumulative_series.pct_change().dropna()
        cumulative_cumprod = (1 + cumulative_returns).cumprod()
        running_max = cumulative_cumprod.cummax()
        cumulative_drawdown = (cumulative_cumprod - running_max) / running_max
        
        return {
            'windows': self.results,
            'summary': {
                'num_windows': len(self.results),
                'total_return_acumulado': (cumulative_equity[-1] - self.config.initial_capital) / self.config.initial_capital,
                'mean_total_return': return_mean,
                'std_total_return': return_std,
                'stability_ratio': stability_ratio,
                'mean_sharpe_ratio': np.mean(sharpe_ratios),
                'std_sharpe_ratio': np.std(sharpe_ratios),
                'mean_max_drawdown': np.mean(max_drawdowns),
                'worst_max_drawdown': np.min(max_drawdowns),
                'mean_win_rate': np.mean(win_rates),
                'cumulative_equity_curve': cumulative_equity,
                'cumulative_max_drawdown': cumulative_drawdown.min() if len(cumulative_drawdown) > 0 else 0
            }
        }
    
    def export_report(self, filepath):
        """Exporta el reporte a CSV"""
        if not self.results:
            logger.warning("No hay resultados para exportar")
            return
        
        # Convertir Path a string si es necesario
        filepath_str = str(filepath)
        
        # Convertir resultados a DataFrame
        df_data = []
        for result in self.results:
            df_data.append({
                'window_id': result['window_id'],
                'train_start_date': result['train_start_date'],
                'train_end_date': result['train_end_date'],
                'test_start_date': result['test_start_date'],
                'test_end_date': result['test_end_date'],
                'total_return': result['total_return'],
                'sharpe_ratio': result['sharpe_ratio'],
                'max_drawdown': result['max_drawdown'],
                'win_rate': result['win_rate'],
                'total_trades': result['total_trades']
            })
        
        df = pd.DataFrame(df_data)
        df.to_csv(filepath_str, index=False)
        logger.info(f"Reporte exportado a {filepath}")
