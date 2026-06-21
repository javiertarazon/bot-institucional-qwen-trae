"""
Motor de cálculo de correlación entre activos
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger()


class AssetClass(Enum):
    CRYPTO = "crypto"
    STOCK = "stock"
    FOREX = "forex"
    COMMODITY = "commodity"
    INDEX = "index"


@dataclass
class AssetData:
    symbol: str
    asset_class: AssetClass
    prices: pd.Series


@dataclass
class CorrelationResult:
    asset_1: str
    asset_2: str
    correlation: float
    is_positive: bool
    is_strong: bool


class CorrelationEngine:
    """Motor para calcular correlaciones entre diferentes activos"""

    def __init__(self):
        # Optional exchange for real data, not required for core correlation calculation
        self.exchange = None

    async def fetch_historical_data(
        self,
        symbol: str,
        asset_class: AssetClass,
        days: int = 365
    ) -> AssetData:
        """Obtiene datos históricos de precios para un activo"""
        try:
            # Usar datos sintéticos para todos los activos (se puede extender con APIs reales)
            logger.info(f"Generating synthetic data for {symbol} ({asset_class.value})")
            dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="D")
            prices = pd.Series(
                np.random.randn(days).cumsum() + (100 if asset_class != AssetClass.CRYPTO else 50000),
                index=dates
            )

            return AssetData(
                symbol=symbol,
                asset_class=asset_class,
                prices=prices
            )
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            raise

    def calculate_correlation_matrix(
        self,
        assets: List[AssetData]
    ) -> pd.DataFrame:
        """Calcula la matriz de correlación entre múltiples activos"""
        data = {}
        for asset in assets:
            # Normalizar las series temporales para compararlas
            data[asset.symbol] = asset.prices.pct_change().dropna()
        
        df = pd.DataFrame(data)
        corr_matrix = df.corr()
        
        logger.info(f"Calculated correlation matrix for {len(assets)} assets")
        return corr_matrix

    def get_correlation_pair(
        self,
        asset1: AssetData,
        asset2: AssetData
    ) -> CorrelationResult:
        """Calcula la correlación entre dos activos específicos"""
        returns1 = asset1.prices.pct_change().dropna()
        returns2 = asset2.prices.pct_change().dropna()
        
        # Alinear las series por fechas
        aligned = pd.concat([returns1, returns2], axis=1, join="inner")
        corr = aligned.corr().iloc[0, 1]
        
        return CorrelationResult(
            asset_1=asset1.symbol,
            asset_2=asset2.symbol,
            correlation=corr,
            is_positive=corr > 0,
            is_strong=abs(corr) > 0.7
        )

    def find_uncorrelated_assets(
        self,
        assets: List[AssetData],
        target_asset: str,
        max_correlation: float = 0.3
    ) -> List[Tuple[str, float]]:
        """Encuentra activos con baja correlación con respecto a un activo objetivo"""
        corr_matrix = self.calculate_correlation_matrix(assets)
        
        if target_asset not in corr_matrix.columns:
            raise ValueError(f"Asset {target_asset} not in correlation matrix")
        
        correlations = corr_matrix[target_asset].sort_values()
        
        uncorrelated = [
            (symbol, corr)
            for symbol, corr in correlations.items()
            if abs(corr) < max_correlation and symbol != target_asset
        ]
        
        logger.info(f"Found {len(uncorrelated)} uncorrelated assets for {target_asset}")
        return uncorrelated

    def get_diversification_recommendations(
        self,
        portfolio_assets: List[AssetData],
        max_correlation: float = 0.4
    ) -> Dict:
        """Genera recomendaciones de diversificación para un portafolio"""
        corr_matrix = self.calculate_correlation_matrix(portfolio_assets)
        
        recommendations = {
            "high_correlation_pairs": [],
            "low_correlation_pairs": [],
            "suggestions": []
        }
        
        # Encontrar pares con alta correlación
        n = len(corr_matrix.columns)
        for i in range(n):
            for j in range(i + 1, n):
                corr = corr_matrix.iloc[i, j]
                asset1 = corr_matrix.columns[i]
                asset2 = corr_matrix.columns[j]
                
                if abs(corr) > 0.7:
                    recommendations["high_correlation_pairs"].append({
                        "assets": (asset1, asset2),
                        "correlation": corr
                    })
                elif abs(corr) < max_correlation:
                    recommendations["low_correlation_pairs"].append({
                        "assets": (asset1, asset2),
                        "correlation": corr
                    })
        
        # Sugerencias para reducir riesgo
        if len(recommendations["high_correlation_pairs"]) > 0:
            recommendations["suggestions"].append(
                "Considera reducir la exposición en activos altamente correlacionados"
            )
        
        logger.info("Generated diversification recommendations")
        return recommendations
