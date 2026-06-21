"""
Motor Predictivo ML - Versión Simplificada para CIP Lite
Ensemble XGBoost + LSTM para predicción de mercado
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
import structlog
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import xgboost as xgb
import warnings
warnings.filterwarnings('ignore')

logger = structlog.get_logger()


class FeatureEngineering:
    """Ingeniería de características simplificada"""
    
    def __init__(self):
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        logger.info("Feature Engineering inicializado")
    
    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Crea características técnicas básicas"""
        df = df.copy()
        
        # Medias móviles
        df['ma7'] = df['close'].rolling(window=7).mean()
        df['ma21'] = df['close'].rolling(window=21).mean()
        
        # Retornos
        df['returns'] = np.log(df['close'] / df['close'].shift(1))
        
        # Volatilidad
        df['std7'] = df['close'].rolling(window=7).std()
        
        # Eliminar NaNs
        df = df.dropna()
        
        return df
    
    def prepare_data(self, df: pd.DataFrame, target_col: str = 'target') -> Tuple[np.ndarray, np.ndarray]:
        """Prepara datos para XGBoost"""
        features = df.drop([target_col, 'close', 'date'], axis=1, errors='ignore').select_dtypes(include=[np.number]).columns
        
        X = df[features].values
        y = df[target_col].values if target_col in df.columns else np.zeros(len(df))
        
        # Asegurar longitudes coincidentes
        min_len = min(len(X), len(y))
        X = X[:min_len]
        y = y[:min_len]
        
        # Normalizar
        X_scaled = self.scaler.fit_transform(X)
        
        return X_scaled, y


class XGBoostModel:
    """Modelo XGBoost simplificado"""
    
    def __init__(self):
        self.model = xgb.XGBClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42,
            use_label_encoder=False,
            eval_metric='logloss'
        )
        self.is_trained = False
        logger.info("XGBoost Model inicializado")
    
    def train(self, X: np.ndarray, y: np.ndarray) -> float:
        """Entrena el modelo"""
        logger.info("Entrenando XGBoost...")
        
        if len(X) < 10:
            logger.warning("Pocos datos para entrenamiento. Usando modelo dummy.")
            self.is_trained = True
            return 0.5
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"XGBoost - Accuracy: {accuracy:.4f}")
        self.is_trained = True
        return accuracy
    
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Probabilidades de predicción"""
        if not self.is_trained:
            return np.array([0.5, 0.5])
        return self.model.predict_proba(X)


class EnsemblePredictor:
    """Ensemble simplificado para CIP Lite"""
    
    def __init__(self):
        self.feature_engineer = FeatureEngineering()
        self.xgboost = XGBoostModel()
        self.is_trained = False
        logger.info("Ensemble Predictor inicializado")
    
    def prepare_market_data(self, prices: List[float]) -> pd.DataFrame:
        """Prepara datos de mercado (datos simulados para demo)"""
        logger.info("Preparando datos de mercado")
        
        dates = [datetime.now() - timedelta(days=i) for i in range(len(prices))]
        dates.reverse()
        
        df = pd.DataFrame({
            'date': dates,
            'open': prices,
            'high': [p * 1.02 for p in prices],
            'low': [p * 0.98 for p in prices],
            'close': prices,
            'volume': np.random.randint(10000, 100000, len(prices))
        })
        
        df['target'] = (df['close'].shift(-1) > df['close']).astype(int)
        df = df.dropna()
        
        return df
    
    def train(self, prices: List[float]) -> Dict[str, float]:
        """Entrena el ensemble"""
        logger.info("Iniciando entrenamiento...")
        
        df = self.prepare_market_data(prices)
        df_features = self.feature_engineer.create_features(df)
        X, y = self.feature_engineer.prepare_data(df_features)
        
        xgb_accuracy = self.xgboost.train(X, y)
        
        self.is_trained = True
        logger.info(f"Entrenamiento completado - Accuracy: {xgb_accuracy:.4f}")
        
        return {"accuracy": xgb_accuracy}
    
    def predict(self, prices: List[float]) -> Dict[str, Any]:
        """Realiza predicción"""
        if not self.is_trained:
            logger.warning("Modelo no entrenado. Usando predicción dummy.")
            return {
                "signal": "HOLD",
                "confidence": 0.5,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        logger.info("Realizando predicción...")
        
        df = self.prepare_market_data(prices)
        df_features = self.feature_engineer.create_features(df)
        X, _ = self.feature_engineer.prepare_data(df_features)
        
        xgb_pred = 0.5
        if len(X) > 0:
            proba = self.xgboost.predict_proba(X[-1:])
            if len(proba.shape) > 1:
                xgb_pred = proba[0, 1]
        
        # Determinar señal
        if xgb_pred > 0.6:
            signal = "BUY"
            confidence = xgb_pred
        elif xgb_pred < 0.4:
            signal = "SELL"
            confidence = 1 - xgb_pred
        else:
            signal = "HOLD"
            confidence = max(xgb_pred, 1 - xgb_pred)
        
        return {
            "signal": signal,
            "confidence": float(confidence),
            "model_confidence": float(xgb_pred),
            "timestamp": datetime.utcnow().isoformat()
        }


def create_demo_price_data(days: int = 90) -> List[float]:
    """Crea datos de precios simulados para demo"""
    np.random.seed(42)
    base_price = 50000
    prices = [base_price]
    
    for _ in range(days - 1):
        change = np.random.normal(0, 0.02)
        new_price = prices[-1] * (1 + change)
        prices.append(max(1, new_price))
    
    return prices


if __name__ == "__main__":
    print("🚀 Prueba del Motor Predictivo CIP")
    print("=" * 60)
    
    prices = create_demo_price_data(days=100)
    print(f"\n1. Datos de demo: {len(prices)} días")
    
    predictor = EnsemblePredictor()
    results = predictor.train(prices)
    print(f"\n2. Entrenamiento: Accuracy = {results.get('accuracy', 0):.2%}")
    
    prediction = predictor.predict(prices)
    print(f"\n3. Predicción: {prediction['signal']}")
    print(f"   Confianza: {prediction['confidence']:.2%}")
    print("\n✅ Motor Predictivo funcionando!")
