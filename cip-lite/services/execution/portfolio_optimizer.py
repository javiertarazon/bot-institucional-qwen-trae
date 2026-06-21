"""
Optimización de Asignación de Portafolio - PyPortfolioOpt
Frontera eficiente de Markowitz, Sharpe Ratio y más
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

import numpy as np
import pandas as pd
from typing import Dict, List
from datetime import datetime, timedelta
import structlog

logger = structlog.get_logger()

try:
    from pypfopt import EfficientFrontier, risk_models, expected_returns
    HAS_PYPO = True
except ImportError:
    HAS_PYPO = False
    logger.warning("PyPortfolioOpt no está instalado. Se usarán asignaciones equitativas.")

class PortfolioAllocator:
    """Asignador de portafolio institucional"""
    def __init__(self, assets: List[str] = ['BTC', 'ETH', 'SOL', 'ADA']):
        self.assets = assets
        logger.info("PortfolioAllocator inicializado", assets=assets)

    def generate_dummy_prices(self, start: str = "2022-06-01", 
                               end: str = "2024-06-01", 
                               base: float = 50000.0) -> pd.DataFrame:
        """Genera precios sintéticos para múltiples activos"""
        dates = pd.date_range(start=start, end=end, freq='D')
        prices = pd.DataFrame(index=dates)
        np.random.seed(42)
        for asset in self.assets:
            # Precios base con volatilidad
            rets = np.random.normal(0.0005, 0.025, size=len(dates))
            price = base * np.cumprod(1 + rets)
            prices[asset] = price
            base = base / 100  # Siguiente activo más barato
        return prices

    def optimize(self, prices: pd.DataFrame, method: str = 'sharpe') -> Dict[str, float]:
        """
        Optimiza la asignación del portafolio
        method: 'sharpe' (max Sharpe Ratio), 'min_vol' (min volatilidad)
        """
        if not HAS_PYPO:
            n = len(self.assets)
            return {a: 1/n for a in self.assets}

        # Calcular rendimientos y covarianza
        mu = expected_returns.mean_historical_return(prices)
        S = risk_models.sample_cov(prices)

        # Optimizar
        ef = EfficientFrontier(mu, S)
        if method == 'sharpe':
            ef.max_sharpe()
        elif method == 'min_vol':
            ef.min_volatility()
        else:
            raise ValueError("Método no reconocido. Usa 'sharpe' o 'min_vol'.")

        weights = ef.clean_weights()
        perf = ef.portfolio_performance(verbose=False)
        logger.info("Asignación optimizada", weights=weights, performance=perf)
        return dict(weights)
