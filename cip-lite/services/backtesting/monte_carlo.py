"""
Motor de Simulaciones Monte Carlo Institucional
Modela múltiples escenarios de precios y variables de mercado
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass
import structlog
from scipy.stats import norm, multivariate_normal
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")

logger = structlog.get_logger()


@dataclass
class MonteCarloConfig:
    """Configuración para Simulaciones Monte Carlo"""
    num_scenarios: int = 10000           # Número de escenarios
    num_days: int = 252                  # Días a simular
    initial_price: float = 50000.0       # Precio inicial
    volatility: Optional[float] = None   # Volatilidad (calculada de datos históricos)
    drift: Optional[float] = None        # Drift (calculado de datos históricos)
    use_multivariate: bool = False       # Usar distribución multivariada para múltiples activos
    correlation_matrix: Optional[np.ndarray] = None  # Matriz de correlación para múltiples activos
    parallel: bool = True                # Ejecutar en paralelo
    num_workers: int = 4                 # Número de workers para paralelismo


class MonteCarloSimulator:
    """Motor de Simulaciones Monte Carlo"""
    
    def __init__(self, config: MonteCarloConfig):
        self.config = config
        self.scenarios: List[np.ndarray] = []
        self.results: Dict[str, Any] = {}
        
    def fit(self, historical_data: pd.DataFrame):
        """Ajusta los parámetros del modelo a datos históricos"""
        logger.info("Ajustando parámetros Monte Carlo a datos históricos")
        
        # Calcular rendimientos logarítmicos
        if 'Close' in historical_data.columns:
            returns = np.log(historical_data['Close'] / historical_data['Close'].shift(1)).dropna()
        else:
            # Si hay múltiples columnas (múltiples activos)
            returns = np.log(historical_data / historical_data.shift(1)).dropna()
        
        # Establecer parámetros si no se proporcionaron
        if self.config.volatility is None:
            if isinstance(returns, pd.Series):
                self.config.volatility = returns.std()
            else:
                self.config.volatility = returns.std().values
        
        if self.config.drift is None:
            if isinstance(returns, pd.Series):
                self.config.drift = returns.mean()
            else:
                self.config.drift = returns.mean().values
        
        # Calcular matriz de correlación si hay múltiples activos
        if self.config.use_multivariate and isinstance(returns, pd.DataFrame):
            self.config.correlation_matrix = returns.corr().values
        
        logger.info(f"Parámetros ajustados: drift={self.config.drift}, volatility={self.config.volatility}")
        
    def simulate_single_scenario(self, seed: Optional[int] = None) -> np.ndarray:
        """Simula un solo escenario"""
        if seed is not None:
            np.random.seed(seed)
        
        dt = 1 / 252  # Paso de tiempo diario
        num_days = self.config.num_days
        
        if isinstance(self.config.initial_price, (int, float)):
            # Simulación para un solo activo
            prices = np.zeros(num_days)
            prices[0] = self.config.initial_price
            
            for t in range(1, num_days):
                # Movimiento Browniano Geométrico
                random_shock = np.random.normal(0, 1)
                prices[t] = prices[t-1] * np.exp(
                    (self.config.drift - 0.5 * self.config.volatility**2) * dt +
                    self.config.volatility * np.sqrt(dt) * random_shock
                )
            
            return prices
        else:
            # Simulación para múltiples activos
            num_assets = len(self.config.initial_price)
            prices = np.zeros((num_days, num_assets))
            prices[0] = self.config.initial_price
            
            if self.config.use_multivariate and self.config.correlation_matrix is not None:
                # Simulación multivariada con correlación
                mean = np.zeros(num_assets)
                cov_matrix = np.outer(self.config.volatility, self.config.volatility) * self.config.correlation_matrix
                
                for t in range(1, num_days):
                    random_shocks = multivariate_normal.rvs(mean, cov_matrix)
                    for i in range(num_assets):
                        prices[t, i] = prices[t-1, i] * np.exp(
                            (self.config.drift[i] - 0.5 * self.config.volatility[i]**2) * dt +
                            self.config.volatility[i] * np.sqrt(dt) * random_shocks[i]
                        )
            else:
                # Simulación independiente por activo
                for t in range(1, num_days):
                    for i in range(num_assets):
                        random_shock = np.random.normal(0, 1)
                        prices[t, i] = prices[t-1, i] * np.exp(
                            (self.config.drift[i] - 0.5 * self.config.volatility[i]**2) * dt +
                            self.config.volatility[i] * np.sqrt(dt) * random_shock
                        )
            
            return prices
    
    def simulate_scenarios(self) -> List[np.ndarray]:
        """Ejecuta todas las simulaciones"""
        logger.info(f"Ejecutando {self.config.num_scenarios} simulaciones Monte Carlo")
        
        self.scenarios = []
        
        if self.config.parallel and self.config.num_scenarios > 100:
            # Ejecución en paralelo
            with ProcessPoolExecutor(max_workers=self.config.num_workers) as executor:
                futures = [
                    executor.submit(self.simulate_single_scenario, seed=i)
                    for i in range(self.config.num_scenarios)
                ]
                
                for future in as_completed(futures):
                    self.scenarios.append(future.result())
                    
                    if len(self.scenarios) % 1000 == 0:
                        logger.debug(f"Simulaciones completadas: {len(self.scenarios)}")
        else:
            # Ejecución secuencial
            for i in range(self.config.num_scenarios):
                self.scenarios.append(self.simulate_single_scenario(seed=i))
                
                if (i + 1) % 1000 == 0:
                    logger.debug(f"Simulaciones completadas: {i + 1}")
        
        logger.info("Todas las simulaciones completadas")
        return self.scenarios
    
    def analyze_scenarios(self, strategy: Optional[Callable] = None) -> Dict[str, Any]:
        """Analiza los resultados de las simulaciones"""
        logger.info("Analizando resultados de Monte Carlo")
        
        if not self.scenarios:
            raise ValueError("Primero debe ejecutar las simulaciones")
        
        # Calcular rendimientos finales
        if isinstance(self.scenarios[0], np.ndarray) and self.scenarios[0].ndim == 1:
            # Un solo activo
            final_prices = [s[-1] for s in self.scenarios]
            returns = [(fp - self.config.initial_price) / self.config.initial_price for fp in final_prices]
        else:
            # Múltiples activos
            final_prices = [s[-1] for s in self.scenarios]
            returns = [np.mean((fp - self.config.initial_price) / self.config.initial_price) for fp in final_prices]
        
        returns_array = np.array(returns)
        
        # Calcular estadísticas clave
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        median_return = np.median(returns_array)
        
        # Percentiles
        percentiles = {
            'p5': np.percentile(returns_array, 5),
            'p25': np.percentile(returns_array, 25),
            'p50': np.percentile(returns_array, 50),
            'p75': np.percentile(returns_array, 75),
            'p95': np.percentile(returns_array, 95)
        }
        
        # Probabilidad de pérdida
        loss_probability = np.mean(returns_array < 0)
        
        # Value at Risk (VaR)
        var_95 = np.percentile(returns_array, 5)
        var_99 = np.percentile(returns_array, 1)
        
        # Conditional VaR (Expected Shortfall)
        cvar_95 = np.mean(returns_array[returns_array <= var_95])
        cvar_99 = np.mean(returns_array[returns_array <= var_99])
        
        self.results = {
            'num_scenarios': self.config.num_scenarios,
            'mean_return': mean_return,
            'std_return': std_return,
            'median_return': median_return,
            'percentiles': percentiles,
            'loss_probability': loss_probability,
            'var_95': var_95,
            'var_99': var_99,
            'cvar_95': cvar_95,
            'cvar_99': cvar_99,
            'all_returns': returns_array
        }
        
        logger.info("Análisis Monte Carlo completado")
        return self.results
    
    def run(
        self, 
        historical_data: pd.DataFrame,
        strategy: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """Ejecuta todo el flujo: ajustar, simular, analizar"""
        self.fit(historical_data)
        self.simulate_scenarios()
        return self.analyze_scenarios(strategy)
    
    def export_scenarios(self, filepath, num_scenarios: int = 100):
        """Exporta un subconjunto de escenarios a CSV"""
        if not self.scenarios:
            logger.warning("No hay escenarios para exportar")
            return
        
        # Convertir Path a string si es necesario
        filepath_str = str(filepath)
        
        export_scenarios = self.scenarios[:num_scenarios]
        
        if isinstance(export_scenarios[0], np.ndarray) and export_scenarios[0].ndim == 1:
            # Un solo activo
            df = pd.DataFrame()
            for i, scenario in enumerate(export_scenarios):
                df[f'scenario_{i}'] = scenario
        else:
            # Múltiples activos - exportar solo el primer activo de cada escenario
            df = pd.DataFrame()
            for i, scenario in enumerate(export_scenarios):
                df[f'scenario_{i}'] = scenario[:, 0]
        
        df.to_csv(filepath_str, index=False)
        logger.info(f"Escenarios exportados a {filepath}")
