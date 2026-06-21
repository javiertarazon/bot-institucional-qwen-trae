"""
Motor Predictivo Optimizado - Hyperopt para XGBoost
Mejora del ratio de ganancia/pérdida y la tasa de aciertos
"""
import sys
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

import numpy as np
import pandas as pd
from typing import Dict, List, Any
from datetime import datetime, timedelta
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import xgboost as xgb
try:
    from hyperopt import fmin, tpe, hp, STATUS_OK, Trials
    HAS_HYPEROPT = True
except ImportError:
    HAS_HYPEROPT = False
import structlog

logger = structlog.get_logger()

class FeatureEngineeringAdvanced:
    """Ingeniería de características avanzada para trading"""
    def __init__(self):
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        logger.info("Feature Engineering Advanced inicializado")

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Medias móviles
        df['ma7'] = df['Close'].rolling(window=7).mean()
        df['ma21'] = df['Close'].rolling(window=21).mean()
        df['ma50'] = df['Close'].rolling(window=50).mean()
        # RSI (14 días)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        # Volatilidad
        df['returns'] = np.log(df['Close'] / df['Close'].shift(1))
        df['volatility'] = df['returns'].rolling(window=21).std() * np.sqrt(365)
        # Drop NaNs
        df = df.dropna()
        return df

    def prepare_data(self, df: pd.DataFrame, target_col: str = 'target') -> tuple[np.ndarray, np.ndarray]:
        features = df.drop([target_col, 'Close'], axis=1, errors='ignore').select_dtypes(include=[np.number]).columns
        X = df[features].values
        y = df[target_col].values if target_col in df.columns else np.zeros(len(df))
        min_len = min(len(X), len(y))
        X = X[:min_len]
        y = y[:min_len]
        X_scaled = self.scaler.fit_transform(X)
        return X_scaled, y

class OptimizedXGBPredictor:
    """Modelo XGBoost optimizado con Hyperopt"""
    def __init__(self):
        self.feature_engineer = FeatureEngineeringAdvanced()
        self.model = None
        self.is_trained = False
        self.space = None
        if HAS_HYPEROPT:
            self.space = {
                'n_estimators': hp.quniform('n_estimators', 50, 300, 50),
                'max_depth': hp.quniform('max_depth', 3, 10, 1),
                'learning_rate': hp.loguniform('learning_rate', np.log(0.01), np.log(0.3)),
                'subsample': hp.uniform('subsample', 0.6, 1.0),
                'colsample_bytree': hp.uniform('colsample_bytree', 0.6, 1.0),
                'gamma': hp.uniform('gamma', 0.0, 1.0),
                'reg_alpha': hp.uniform('reg_alpha', 0.0, 1.0),
                'reg_lambda': hp.uniform('reg_lambda', 0.5, 2.0)
            }
        logger.info("OptimizedXGBPredictor inicializado")

    def objective(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Función objetivo para Hyperopt (minimizar 1 - accuracy)"""
        params['n_estimators'] = int(params['n_estimators'])
        params['max_depth'] = int(params['max_depth'])
        params['use_label_encoder'] = False
        params['eval_metric'] = 'logloss'
        params['random_state'] = 42

        model = xgb.XGBClassifier(**params)
        tscv = TimeSeriesSplit(n_splits=5)
        scores = []

        for train_idx, test_idx in tscv.split(self.X):
            X_train, X_test = self.X[train_idx], self.X[test_idx]
            y_train, y_test = self.y[train_idx], self.y[test_idx]
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            scores.append(acc)

        mean_acc = np.mean(scores)
        return {'loss': 1 - mean_acc, 'status': STATUS_OK}

    def optimize(self, X: np.ndarray, y: np.ndarray, max_evals: int = 20):
        """Ejecuta la optimización de hiperparámetros"""
        self.X = X
        self.y = y
        trials = Trials()
        best = fmin(
            fn=self.objective,
            space=self.space,
            algo=tpe.suggest,
            max_evals=max_evals,
            trials=trials,
            rstate=np.random.default_rng(42)
        )

        # Convertir tipos
        best['n_estimators'] = int(best['n_estimators'])
        best['max_depth'] = int(best['max_depth'])
        best['use_label_encoder'] = False
        best['eval_metric'] = 'logloss'
        best['random_state'] = 42

        logger.info("Mejores hiperparámetros encontrados", best_params=best)
        self.model = xgb.XGBClassifier(**best)
        self.model.fit(X, y)
        self.is_trained = True
        logger.info("Modelo optimizado entrenado")
        return best

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.is_trained:
            raise ValueError("Modelo no entrenado. Primero llama a optimize().")
        return self.model.predict_proba(X)

class OptimizedStrategy:
    """Estrategia optimizada basada en el modelo mejorado"""
    def __init__(self):
        self.predictor = OptimizedXGBPredictor()
        self.feature_engineer = FeatureEngineeringAdvanced()
        self.is_initialized = False
        logger.info("OptimizedStrategy inicializada")

    def prepare_data(self, prices: List[float]) -> pd.DataFrame:
        dates = [datetime.now() - timedelta(days=i) for i in range(len(prices))]
        dates.reverse()
        df = pd.DataFrame({
            'Date': dates,
            'Open': prices,
            'High': [p * 1.02 for p in prices],
            'Low': [p * 0.98 for p in prices],
            'Close': prices,
            'Volume': np.random.randint(10000, 100000, len(prices))
        })
        df.set_index('Date', inplace=True)
        df['target'] = (df['Close'].shift(-1) > df['Close']).astype(int)
        df = df.dropna()
        return df

    def __call__(self, df_hist: pd.DataFrame) -> str:
        """Ejecuta la estrategia: retorna 'BUY', 'SELL' o 'HOLD'"""
        # Asegurar que tenemos suficientes datos
        if len(df_hist) < 100:
            return 'HOLD'

        # Preparar características y entrenar si es la primera vez
        if not self.is_initialized:
            df_full = self.prepare_data(df_hist['Close'].values)
            df_feat = self.feature_engineer.create_features(df_full)
            X, y = self.feature_engineer.prepare_data(df_feat)
            self.predictor.optimize(X, y, max_evals=10)
            self.is_initialized = True

        # Predecir el siguiente paso
        df_feat = self.feature_engineer.create_features(df_hist.tail(100))
        X, _ = self.feature_engineer.prepare_data(df_feat)
        if len(X) < 1:
            return 'HOLD'
        proba = self.predictor.predict_proba(X[-1:])
        prob_up = proba[0, 1]

        if prob_up > 0.6:
            return 'BUY'
        elif prob_up < 0.4:
            return 'SELL'
        else:
            return 'HOLD'
