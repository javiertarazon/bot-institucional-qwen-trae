"""
Marco de Pruebas Out-of-Sample Rigurosas
Segrega datos irreversiblemente y aplica tests estadísticos
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import structlog
from scipy import stats
from enum import Enum

logger = structlog.get_logger()


class MarketRegime(Enum):
    """Tipos de regímenes de mercado"""
    BULL = "bull"           # Mercado alcista
    BEAR = "bear"           # Mercado bajista
    HIGH_VOLATILITY = "high_vol"  # Alta volatilidad
    NORMAL = "normal"       # Mercado normal


@dataclass
class OutOfSampleConfig:
    """Configuración para Pruebas Out-of-Sample"""
    test_size_pct: float = 0.3           # Porcentaje de datos para prueba
    num_independent_test_sets: int = 3   # Número de conjuntos de prueba independientes
    min_return_threshold: float = 0.0    # Rendimiento mínimo aceptable
    max_drawdown_threshold: float = -0.2 # Máximo drawdown aceptable
    significance_level: float = 0.05     # Nivel de significancia para tests


class OutOfSampleTester:
    """Motor de Pruebas Out-of-Sample"""
    
    def __init__(self, config: OutOfSampleConfig):
        self.config = config
        self.datasets: Dict[str, pd.DataFrame] = {}
        self.results: Dict[str, Any] = {}
        
    def split_data(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Divide los datos en entrenamiento y múltiples conjuntos de prueba"""
        logger.info("Dividiendo datos para Out-of-Sample Testing")
        
        total_size = len(data)
        test_size = int(total_size * self.config.test_size_pct)
        
        # Asegurar que no haya data leakage
        datasets = {}
        
        # Conjunto de entrenamiento (primeros datos)
        train_size = total_size - test_size * self.config.num_independent_test_sets
        if train_size < 0:
            raise ValueError("Demasiados conjuntos de prueba para el tamaño de datos")
        
        datasets['train'] = data.iloc[:train_size].copy()
        
        # Conjuntos de prueba independientes (sin superposición)
        for i in range(self.config.num_independent_test_sets):
            start_idx = train_size + i * test_size
            end_idx = train_size + (i + 1) * test_size
            datasets[f'test_{i}'] = data.iloc[start_idx:end_idx].copy()
        
        self.datasets = datasets
        logger.info(f"Datos divididos: 1 train + {self.config.num_independent_test_sets} test sets")
        return datasets
    
    def identify_market_regimes(self, data: pd.DataFrame) -> Dict[MarketRegime, pd.DataFrame]:
        """Identifica diferentes regímenes de mercado en los datos"""
        logger.info("Identificando regímenes de mercado")
        
        if 'Close' not in data.columns:
            raise ValueError("Se requiere columna 'Close' para identificar regímenes")
        
        # Copiar datos para preservar el índice
        df = data.copy()
        
        # Calcular rendimientos y volatilidad
        df['returns'] = df['Close'].pct_change()
        df['volatility'] = df['returns'].rolling(window=21).std()
        
        # Identificar tendencia (bull/bear)
        df['ma_long'] = df['Close'].rolling(window=100).mean()
        df['trend_up'] = df['Close'] > df['ma_long']
        
        # Identificar volatilidad alta (solo donde tenemos datos de volatilidad)
        valid_df = df.dropna(subset=['volatility'])
        if len(valid_df) == 0:
            return {}
            
        vol_threshold = valid_df['volatility'].mean() + valid_df['volatility'].std()
        df['high_vol'] = df['volatility'] > vol_threshold
        
        regimes = {}
        
        # Eliminar filas con NaN en las máscaras
        df = df.dropna(subset=['trend_up', 'high_vol'])
        
        # Mercado alcista
        bull_mask = df['trend_up'] & ~df['high_vol']
        if bull_mask.sum() > 0:
            regimes[MarketRegime.BULL] = df.loc[bull_mask, ['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        # Mercado bajista
        bear_mask = ~df['trend_up'] & ~df['high_vol']
        if bear_mask.sum() > 0:
            regimes[MarketRegime.BEAR] = df.loc[bear_mask, ['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        # Alta volatilidad
        high_vol_mask = df['high_vol']
        if high_vol_mask.sum() > 0:
            regimes[MarketRegime.HIGH_VOLATILITY] = df.loc[high_vol_mask, ['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        # Mercado normal
        normal_mask = ~df['high_vol']
        if normal_mask.sum() > 0:
            regimes[MarketRegime.NORMAL] = df.loc[normal_mask, ['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        
        logger.info(f"Identificados {len(regimes)} regímenes de mercado")
        return regimes
    
    def diebold_mariano_test(
        self, 
        actual_returns: np.ndarray, 
        model_returns: np.ndarray,
        benchmark_returns: np.ndarray
    ) -> Dict[str, Any]:
        """
        Test de Diebold-Mariano para comparar rendimientos
        Compara el rendimiento del modelo vs un benchmark
        """
        logger.info("Ejecutando Test de Diebold-Mariano")
        
        # Calcular errores de predicción (diferencias de rendimiento)
        loss_model = -model_returns  # Usamos pérdida negativa
        loss_benchmark = -benchmark_returns
        
        # Diferencia de pérdidas
        loss_diff = loss_model - loss_benchmark
        
        # Calcular estadístico DM
        n = len(loss_diff)
        mean_diff = np.mean(loss_diff)
        var_diff = np.var(loss_diff, ddof=1)
        
        # Corrección de autocorrelación (simplificada)
        # En la práctica, se usa HAC estimator
        dm_stat = mean_diff / np.sqrt(var_diff / n)
        
        # Valor p (distribución normal estándar)
        p_value = 2 * (1 - stats.norm.cdf(abs(dm_stat)))
        
        return {
            'dm_statistic': dm_stat,
            'p_value': p_value,
            'significant': p_value < self.config.significance_level,
            'model_better': dm_stat < 0
        }
    
    def test_on_dataset(
        self,
        dataset_name: str,
        data: pd.DataFrame,
        strategy: Callable,
        benchmark_strategy: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Prueba una estrategia en un conjunto de datos específico"""
        from .engine import BacktestEngine, BacktestConfig
        
        logger.info(f"Probando estrategia en {dataset_name}")
        
        # Ejecutar backtesting para la estrategia
        backtest_config = BacktestConfig()
        engine = BacktestEngine(backtest_config)
        result = engine.run(data, strategy)
        
        # Ejecutar benchmark si se proporciona
        benchmark_result = None
        if benchmark_strategy:
            benchmark_engine = BacktestEngine(backtest_config)
            benchmark_result = benchmark_engine.run(data, benchmark_strategy)
        
        # Test de Diebold-Mariano si hay benchmark
        dm_test = None
        if benchmark_result:
            # Obtener series de rendimiento
            equity_strategy = pd.Series(result['equity_curve']).pct_change().dropna()
            equity_benchmark = pd.Series(benchmark_result['equity_curve']).pct_change().dropna()
            
            # Alinear series
            min_len = min(len(equity_strategy), len(equity_benchmark))
            dm_test = self.diebold_mariano_test(
                np.zeros(min_len),  # No necesitamos actual
                equity_strategy.values[:min_len],
                equity_benchmark.values[:min_len]
            )
        
        # Verificar umbrales
        passes_thresholds = (
            result['total_return'] >= self.config.min_return_threshold and
            result['max_drawdown'] >= self.config.max_drawdown_threshold
        )
        
        return {
            'dataset': dataset_name,
            'strategy_result': result,
            'benchmark_result': benchmark_result,
            'diebold_mariano_test': dm_test,
            'passes_thresholds': passes_thresholds
        }
    
    def run(
        self,
        data: pd.DataFrame,
        strategy: Callable,
        benchmark_strategy: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Ejecuta todas las pruebas Out-of-Sample"""
        logger.info("Iniciando pruebas Out-of-Sample")
        
        # Dividir datos
        self.split_data(data)
        
        # Identificar regímenes en datos de prueba
        all_test_data = pd.concat([
            self.datasets[f'test_{i}'] 
            for i in range(self.config.num_independent_test_sets)
        ])
        regimes = self.identify_market_regimes(all_test_data)
        
        # Ejecutar pruebas en conjuntos de prueba independientes
        test_results = []
        for i in range(self.config.num_independent_test_sets):
            result = self.test_on_dataset(
                f'test_{i}',
                self.datasets[f'test_{i}'],
                strategy,
                benchmark_strategy
            )
            test_results.append(result)
        
        # Ejecutar pruebas por régimen
        regime_results = {}
        for regime, regime_data in regimes.items():
            result = self.test_on_dataset(
                f'regime_{regime.value}',
                regime_data,
                strategy,
                benchmark_strategy
            )
            regime_results[regime.value] = result
        
        # Resultado consolidado
        all_passed = all(r['passes_thresholds'] for r in test_results)
        all_regimes_passed = all(r['passes_thresholds'] for r in regime_results.values())
        
        self.results = {
            'test_sets': test_results,
            'regime_tests': regime_results,
            'summary': {
                'all_test_sets_passed': all_passed,
                'all_regimes_passed': all_regimes_passed,
                'num_test_sets': len(test_results),
                'num_regimes_tested': len(regime_results),
                'mean_total_return': np.mean([r['strategy_result']['total_return'] for r in test_results]),
                'mean_sharpe_ratio': np.mean([r['strategy_result']['sharpe_ratio'] for r in test_results]),
                'mean_max_drawdown': np.mean([r['strategy_result']['max_drawdown'] for r in test_results])
            }
        }
        
        logger.info("Pruebas Out-of-Sample completadas")
        return self.results
    
    def export_report(self, filepath):
        """Exporta el reporte de pruebas"""
        if not self.results:
            logger.warning("No hay resultados para exportar")
            return
        
        # Convertir Path a string si es necesario
        filepath_str = str(filepath)
        
        # Exportar resultados de test sets
        test_data = []
        for result in self.results['test_sets']:
            test_data.append({
                'dataset': result['dataset'],
                'total_return': result['strategy_result']['total_return'],
                'sharpe_ratio': result['strategy_result']['sharpe_ratio'],
                'max_drawdown': result['strategy_result']['max_drawdown'],
                'passes_thresholds': result['passes_thresholds']
            })
        
        df_test = pd.DataFrame(test_data)
        df_test.to_csv(filepath_str.replace('.csv', '_test_sets.csv'), index=False)
        
        # Exportar resultados de regímenes
        regime_data = []
        for regime, result in self.results['regime_tests'].items():
            regime_data.append({
                'regime': regime,
                'total_return': result['strategy_result']['total_return'],
                'sharpe_ratio': result['strategy_result']['sharpe_ratio'],
                'max_drawdown': result['strategy_result']['max_drawdown'],
                'passes_thresholds': result['passes_thresholds']
            })
        
        df_regime = pd.DataFrame(regime_data)
        df_regime.to_csv(filepath_str.replace('.csv', '_regimes.csv'), index=False)
        
        logger.info(f"Reporte exportado a {filepath}")
