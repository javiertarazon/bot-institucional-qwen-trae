"""
ONNX Regime Strategy - CIP Lite v2.0
Estrategia de régimen de mercado usando modelo ONNX (migrada desde
backtest_profesional_cline.py para centralizar todas las estrategias en
services/strategies y ser usable por el runner único run_full_backtest.py).
"""
import os
import pickle
import numpy as np
import pandas as pd
from typing import Optional, Dict, Any

from services.strategies.base_strategy import BaseStrategy, StrategySignal


class ONNXRegimeStrategy(BaseStrategy):
    """
    Clasifica el régimen (MOMENTUM / LATERAL) con ONNX y aplica la estrategia
    correspondiente (tendencia o mean reversion). Compatible con el
    StrategyRegistry y el BacktestEngine.
    """

    name = "onnx_regime"

    def __init__(self, model_path: str = None, scaler_path: str = None,
                 model_dir: str = None):
        if model_dir is None:
            model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "models")
        self.model_path = model_path or os.path.join(model_dir, "regime_model.onnx")
        self.scaler_path = scaler_path or os.path.join(model_dir, "scaler.pkl")
        self.model = None
        self.scaler = None
        self.input_name = None
        self._load_model()

    @property
    def required_params(self) -> list:
        return []

    def _load_model(self):
        if os.path.exists(self.scaler_path):
            try:
                with open(self.scaler_path, "rb") as f:
                    self.scaler = pickle.load(f)
            except Exception:
                self.scaler = None
        if os.path.exists(self.model_path):
            try:
                import onnxruntime as ort
                so = ort.SessionOptions()
                so.intra_op_num_threads = 2
                so.inter_op_num_threads = 2
                so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
                self.model = ort.InferenceSession(
                    self.model_path, so, providers=["CPUExecutionProvider"]
                )
                self.input_name = self.model.get_inputs()[0].name
            except Exception:
                self.model = None

    @staticmethod
    def _normalize(df: pd.DataFrame) -> pd.DataFrame:
        mapping = {"open": "Open", "high": "High", "low": "Low",
                   "close": "Close", "volume": "Volume"}
        rename = {c: mapping[c.lower()] for c in df.columns if c.lower() in mapping}
        return df.rename(columns=rename)

    def _compute_features(self, df: pd.DataFrame) -> Optional[np.ndarray]:
        if len(df) < 50:
            return None
        df = self._normalize(df)
        close = df["Close"].values
        high = df["High"].values
        low = df["Low"].values
        volume = df["Volume"].values
        open_p = df["Open"].values

        cs = pd.Series(close)
        hs = pd.Series(high)
        ls = pd.Series(low)
        vs = pd.Series(volume)

        # RSI(14)
        delta = cs.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        # ATR ratio
        tr = pd.concat([hs - ls, (hs - cs.shift()).abs(), (ls - cs.shift()).abs()],
                       axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        atr_sma = atr.rolling(50).mean()

        # EMA distance
        ema_9 = cs.ewm(span=9).mean().iloc[-1]
        ema_21 = cs.ewm(span=21).mean().iloc[-1]

        # Body / volume / BB / ADX / MACD / Stoch
        body = abs(close[-1] - open_p[-1])
        candle_range = high[-1] - low[-1]
        vol_sma_20 = vs.rolling(20).mean()
        bb_sma = cs.rolling(20).mean()
        bb_std = cs.rolling(20).std()
        plus_dm = hs.diff(); minus_dm = -ls.diff()
        plus_dm[plus_dm < 0] = 0; minus_dm[minus_dm < 0] = 0
        tr_sma = tr.rolling(14).mean()
        plus_di = 100 * (plus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
        minus_di = 100 * (minus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
        dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
        ema_12 = cs.ewm(span=12).mean(); ema_26 = cs.ewm(span=26).mean()
        macd = ema_12 - ema_26; signal = macd.ewm(span=9).mean()

        feats = {
            "rsi_14": rsi.iloc[-1],
            "rsi_delta": rsi.diff().iloc[-1] if len(rsi) > 1 else 0,
            "atr_ratio": (atr / atr_sma.replace(0, np.nan)).iloc[-1],
            "ema_9_21_dist": (ema_9 - ema_21) / close[-1],
            "candle_body_pct": (body / candle_range * 100) if candle_range > 0 else 0,
            "volume_ratio": (volume[-1] / vol_sma_20.iloc[-1]) if vol_sma_20.iloc[-1] > 0 else 1.0,
            "bb_position": ((close[-1] - (bb_sma - 2 * bb_std).iloc[-1]) /
                            ((bb_sma + 2 * bb_std).iloc[-1] - (bb_sma - 2 * bb_std).iloc[-1])) if bb_std.iloc[-1] > 0 else 0.5,
            "adx": dx.rolling(14).mean().iloc[-1],
            "macd_hist": (macd - signal).iloc[-1],
            "stoch_k": 100 * (close[-1] - ls.rolling(14).min().iloc[-1]) /
                       (hs.rolling(14).max().iloc[-1] - ls.rolling(14).min().iloc[-1]) if hs.rolling(14).max().iloc[-1] > ls.rolling(14).min().iloc[-1] else 50,
        }
        names = list(feats.keys())
        arr = np.array([[feats.get(f, 0) for f in names]], dtype=np.float32)
        return np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)

    def _predict_regime(self, df: pd.DataFrame) -> str:
        if self.model is None:
            return "LATERAL"
        x = self._compute_features(df)
        if x is None:
            return "LATERAL"
        if self.scaler is not None:
            x = self.scaler.transform(x).astype(np.float32)
        try:
            pred = self.model.run(None, {self.input_name: x})[0]
            return "MOMENTUM" if pred[0][0] == 1 else "LATERAL"
        except Exception:
            return "LATERAL"

    def __call__(self, df: pd.DataFrame, symbol: str) -> Optional[StrategySignal]:
        if len(df) < 50:
            return StrategySignal(symbol=symbol, signal="HOLD", confidence=0.5,
                                  strategy_name=self.name)
        regime = self._predict_regime(df)
        df = self._normalize(df)
        close = df["Close"]
        if regime == "MOMENTUM":
            ma_7 = close.tail(7).mean()
            ma_21 = close.tail(21).mean()
            if ma_7 > ma_21 * 1.005:
                return StrategySignal(symbol=symbol, signal="BUY", confidence=0.75,
                                      strategy_name=self.name, entry_price=close.iloc[-1])
            elif ma_7 < ma_21 * 0.995:
                return StrategySignal(symbol=symbol, signal="SELL", confidence=0.75,
                                      strategy_name=self.name, entry_price=close.iloc[-1])
        else:
            bb_sma = close.tail(20).mean()
            bb_std = close.tail(20).std()
            upper = bb_sma + 2 * bb_std
            lower = bb_sma - 2 * bb_std
            price = close.iloc[-1]
            if price < lower:
                return StrategySignal(symbol=symbol, signal="BUY", confidence=0.7,
                                      strategy_name=self.name, entry_price=price)
            elif price > upper:
                return StrategySignal(symbol=symbol, signal="SELL", confidence=0.7,
                                      strategy_name=self.name, entry_price=price)
        return StrategySignal(symbol=symbol, signal="HOLD", confidence=0.5,
                              strategy_name=self.name)