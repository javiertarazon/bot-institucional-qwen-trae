#!/usr/bin/env python3
"""
🧠 ONNX Trainer Profesional - CIP v2.0
Entrena modelo XGBoost con datos históricos REALES de Binance (CCXT)
Split temporal 70/30 SIN SOLAPAMIENTO
Exporta a ONNX para inferencia ultrarrápida
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import xgboost as xgb
from onnxmltools.convert import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType
from pathlib import Path
from datetime import datetime, timedelta
import json
import pickle
import warnings
warnings.filterwarnings("ignore")

# ==================== CONFIGURACIÓN ====================
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "historical"
MODEL_DIR = BASE_DIR / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_ONNX_PATH = MODEL_DIR / "regime_model.onnx"
MODEL_XGB_PATH = MODEL_DIR / "regime_model.json"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
FEATURES_META_PATH = MODEL_DIR / "features_meta.json"

# Split temporal
TRAIN_SPLIT = 0.70  # 70% entrenamiento, 30% backtesting
VAL_SPLIT = 0.15    # 15% validación dentro del 70% de entrenamiento

# Features a calcular
FEATURE_NAMES = [
    'rsi_14',
    'rsi_delta',
    'atr_ratio',
    'ema_9_21_dist',
    'candle_body_pct',
    'volume_ratio',
    'bb_position',
    'adx',
    'macd_hist',
    'stoch_k',
]

NUM_FEATURES = len(FEATURE_NAMES)

# Labeling: forward return a N velas
FORWARD_PERIODS = 5  # mirar 5 velas hacia adelante
RETURN_THRESHOLD = 0.005  # 0.5% para considerar MOMENTUM


def load_historical_data(symbols: list = None) -> pd.DataFrame:
    """
    Carga datos históricos desde archivos Parquet.
    """
    if symbols is None:
        # Cargar todos los disponibles
        parquet_files = list(DATA_DIR.glob("*.parquet"))
        symbols = [f.stem.replace('_', '/') for f in parquet_files]
    
    all_dfs = []
    
    for symbol in symbols:
        parquet_path = DATA_DIR / f"{symbol.replace('/', '_')}.parquet"
        if not parquet_path.exists():
            print(f"⚠️  Datos no encontrados para {symbol}. Ejecuta primero:")
            print(f"   python 01_data_ingestion/historical_downloader.py --symbols {symbol}")
            continue
        
        df = pd.read_parquet(parquet_path)
        if df.empty:
            continue
        
        df['symbol'] = symbol
        all_dfs.append(df)
        print(f"   📊 {symbol}: {len(df)} velas ({df.index[0].date()} → {df.index[-1].date()})")
    
    if not all_dfs:
        raise FileNotFoundError(
            "No hay datos históricos. Descárgalos primero:\n"
            "  python 01_data_ingestion/historical_downloader.py"
        )
    
    combined = pd.concat(all_dfs, axis=0)
    combined.sort_index(inplace=True)
    
    print(f"\n📦 Dataset combinado: {len(combined)} filas, {combined['symbol'].nunique()} símbolos")
    return combined


def compute_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula todas las features técnicas para el modelo ONNX.
    No usa look-ahead: solo datos hasta la vela actual.
    """
    df = df.copy()
    
    # Asegurar que tenemos suficientes datos
    if len(df) < 50:
        return pd.DataFrame()
    
    close = df['close']
    high = df['high']
    low = df['low']
    volume = df['volume']
    open_p = df['open']
    
    # 1. RSI(14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # 2. RSI Delta (cambio en RSI)
    df['rsi_delta'] = df['rsi_14'].diff()
    
    # 3. ATR(14) ratio vs media
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    atr_sma = atr.rolling(50).mean()
    df['atr_ratio'] = atr / atr_sma.replace(0, np.nan)
    
    # 4. EMA distance (9 vs 21)
    ema_9 = close.ewm(span=9).mean()
    ema_21 = close.ewm(span=21).mean()
    df['ema_9_21_dist'] = (ema_9 - ema_21) / close
    
    # 5. Cuerpo de vela %
    body = (close - open_p).abs()
    candle_range = high - low
    df['candle_body_pct'] = body / candle_range.replace(0, np.nan) * 100
    
    # 6. Volumen relativo (vs media 20)
    vol_sma_20 = volume.rolling(20).mean()
    df['volume_ratio'] = volume / vol_sma_20.replace(0, np.nan)
    
    # 7. Bollinger Bands position
    bb_sma = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_sma + 2 * bb_std
    bb_lower = bb_sma - 2 * bb_std
    df['bb_position'] = (close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
    
    # 8. ADX (Average Directional Index)
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    minus_dm = minus_dm.abs()
    
    tr_sma = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / tr_sma.replace(0, np.nan))
    dx = (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan) * 100
    df['adx'] = dx.rolling(14).mean()
    
    # 9. MACD histogram
    ema_12 = close.ewm(span=12).mean()
    ema_26 = close.ewm(span=26).mean()
    macd = ema_12 - ema_26
    signal = macd.ewm(span=9).mean()
    df['macd_hist'] = macd - signal
    
    # 10. Stochastic %K
    k_period = 14
    low_k = low.rolling(k_period).min()
    high_k = high.rolling(k_period).max()
    df['stoch_k'] = 100 * (close - low_k) / (high_k - low_k).replace(0, np.nan)
    
    # Limpiar NaN (primeras filas donde no hay suficientes datos)
    df = df.replace([np.inf, -np.inf], np.nan)
    
    return df


def create_labels(df: pd.DataFrame, forward_periods: int = FORWARD_PERIODS,
                  threshold: float = RETURN_THRESHOLD) -> pd.Series:
    """
    Crea labels basados en forward returns.
    1 = MOMENTUM (retorno futuro > threshold)
    0 = LATERAL (retorno futuro <= threshold)
    
    CRÍTICO: Esto NO es look-ahead porque la label se usa SOLO en entrenamiento.
    En inferencia, el modelo predice sin conocer el futuro.
    """
    # Forward return a N velas
    forward_return = df['close'].shift(-forward_periods) / df['close'] - 1
    
    # Label: 1 si el retorno futuro supera el threshold
    labels = (forward_return.abs() > threshold).astype(int)
    
    return labels


def temporal_train_test_split(df: pd.DataFrame, train_pct: float = TRAIN_SPLIT):
    """
    Divide datos en entrenamiento y prueba SIN look-ahead.
    Los datos se ordenan por tiempo: primeros train_pct% para entrenar,
    últimos (1-train_pct)% para probar.
    """
    # Ordenar por timestamp
    df = df.sort_index()
    
    # Split temporal
    split_idx = int(len(df) * train_pct)
    
    train_df = df.iloc[:split_idx].copy()
    test_df = df.iloc[split_idx:].copy()
    
    print(f"\n📅 Split temporal 70/30:")
    print(f"   🏋️  Entrenamiento: {train_df.index[0].date()} → {train_df.index[-1].date()} ({len(train_df)} filas)")
    print(f"   🧪  Backtesting:   {test_df.index[0].date()} → {test_df.index[-1].date()} ({len(test_df)} filas)")
    
    return train_df, test_df


def prepare_training_data(df: pd.DataFrame) -> tuple:
    """
    Prepara datos para entrenamiento: calcula features y labels.
    """
    print("\n🔧 Calculando features técnicas...")
    df_features = compute_features(df)
    
    if df_features.empty:
        raise ValueError("No se pudieron calcular features. ¿Datos suficientes?")
    
    print(f"   Features calculadas: {len(FEATURE_NAMES)}")
    for f in FEATURE_NAMES:
        non_null = df_features[f].notna().sum()
        print(f"      {f:20s}: {non_null:6d} valores no-null")
    
    # Crear labels
    print("\n🏷️  Creando labels (forward returns)...")
    labels = create_labels(df_features)
    
    # Eliminar filas con NaN (donde no hay suficientes datos históricos o forward)
    valid_mask = df_features[FEATURE_NAMES].notna().all(axis=1) & labels.notna()
    X = df_features.loc[valid_mask, FEATURE_NAMES].values.astype(np.float32)
    y = labels[valid_mask].values
    
    # Mostrar distribución de clases
    momentum_pct = y.sum() / len(y) * 100
    lateral_pct = (1 - y.sum() / len(y)) * 100
    print(f"\n📊 Distribución de clases:")
    print(f"   🔥 MOMENTUM (1): {y.sum():6d} ({momentum_pct:.1f}%)")
    print(f"   ⏸️  LATERAL  (0): {len(y)-y.sum():6d} ({lateral_pct:.1f}%)")
    
    return X, y, df_features.loc[valid_mask]


def train_model(X_train, y_train, X_val, y_val):
    """
    Entrena modelo XGBoost con validación.
    """
    print("\n🧠 Entrenando modelo XGBoost...")
    
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        gamma=0.1,
        reg_alpha=0.1,
        reg_lambda=1.0,
        use_label_encoder=False,
        eval_metric='logloss',
        early_stopping_rounds=20,
        n_jobs=4,
        random_state=42,
    )
    
    model.fit(
        X_train, y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=False
    )
    
    # Métricas
    train_acc = model.score(X_train, y_train)
    val_acc = model.score(X_val, y_val)
    
    print(f"\n📊 Precisión:")
    print(f"   🏋️  Entrenamiento: {train_acc*100:.2f}%")
    print(f"   ✅ Validación:    {val_acc*100:.2f}%")
    
    # Feature importance
    print(f"\n📊 Importancia de Features:")
    importances = model.feature_importances_
    for name, imp in sorted(zip(FEATURE_NAMES, importances), 
                            key=lambda x: x[1], reverse=True):
        print(f"   {name:20s}: {imp*100:.1f}%")
    
    return model, train_acc, val_acc


def export_to_onnx(model, output_path: Path):
    """
    Exporta modelo XGBoost a ONNX.
    """
    print(f"\n📦 Exportando a ONNX...")
    
    initial_type = [('float_input', FloatTensorType([None, NUM_FEATURES]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type, target_opset=12)
    
    with open(output_path, "wb") as f:
        f.write(onnx_model.SerializeToString())
    
    size_kb = output_path.stat().st_size / 1024
    print(f"   ✅ Modelo ONNX guardado: {output_path}")
    print(f"   📏 Tamaño: {size_kb:.2f} KB")
    
    return output_path


def save_scaler(X_train: np.ndarray, output_path: Path):
    """
    Guarda el scaler (media y std) para normalizar features en inferencia.
    """
    from sklearn.preprocessing import StandardScaler
    
    scaler = StandardScaler()
    scaler.fit(X_train)
    
    with open(output_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    print(f"   ✅ Scaler guardado: {output_path}")
    print(f"   📊 Medias: {scaler.mean_[:4]}...")
    print(f"   📊 Stds:   {scaler.scale_[:4]}...")
    
    return scaler


def save_features_meta(output_path: Path):
    """Guarda metadatos de features para referencia"""
    meta = {
        'feature_names': FEATURE_NAMES,
        'num_features': NUM_FEATURES,
        'forward_periods': FORWARD_PERIODS,
        'return_threshold': RETURN_THRESHOLD,
        'train_split': TRAIN_SPLIT,
        'training_date': datetime.now().isoformat(),
        'description': 'Features técnicas para clasificación de régimen de mercado',
    }
    
    with open(output_path, 'w') as f:
        json.dump(meta, f, indent=2)
    
    print(f"   ✅ Metadatos guardados: {output_path}")


def test_inference(model_path: Path, scaler_path: Path, X_test: np.ndarray):
    """
    Prueba de inferencia con el modelo ONNX exportado.
    """
    print("\n🧪 [Test] Probando inferencia ONNX...")
    
    try:
        import onnxruntime as ort
        
        # Cargar scaler
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        
        # Cargar modelo ONNX
        sess_options = ort.SessionOptions()
        sess_options.intra_op_num_threads = 2
        sess_options.inter_op_num_threads = 2
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        session = ort.InferenceSession(
            str(model_path),
            sess_options,
            providers=['CPUExecutionProvider']
        )
        
        input_name = session.get_inputs()[0].name
        
        # Normalizar datos de prueba
        X_test_scaled = scaler.transform(X_test[:100])  # Solo 100 muestras
        
        # Inferencia batch
        import time
        start = time.time()
        predictions = session.run(None, {input_name: X_test_scaled})[0]
        elapsed = (time.time() - start) * 1000
        
        # Estadísticas
        momentum_pred = (predictions == 1).sum()
        lateral_pred = (predictions == 0).sum()
        
        print(f"   ✅ Inferencia exitosa: {len(predictions)} predicciones en {elapsed:.2f}ms")
        print(f"   📊 Predicciones: MOMENTUM={momentum_pred}, LATERAL={lateral_pred}")
        print(f"   ⚡ Latencia promedio: {elapsed/len(predictions):.4f}ms/predicción")
        
        return True
        
    except ImportError:
        print("   ⚠️  onnxruntime no instalado. Instalar: pip install onnxruntime")
        return False
    except Exception as e:
        print(f"   ❌ Error en test: {e}")
        return False


def main(symbols: list = None):
    """
    Pipeline completo de entrenamiento.
    """
    print("=" * 70)
    print("🧠 ONNX TRAINER PROFESIONAL - CIP v2.0")
    print("   Datos reales Binance | Split 70/30 | XGBoost → ONNX")
    print("=" * 70)
    
    # 1. Cargar datos históricos
    print("\n📥 Cargando datos históricos...")
    df = load_historical_data(symbols)
    
    # 2. Split temporal 70/30 (SIN SOLAPAMIENTO)
    train_df, test_df = temporal_train_test_split(df)
    
    # 3. Preparar datos de entrenamiento
    print("\n🔧 Preparando datos de entrenamiento...")
    X_train, y_train, train_features = prepare_training_data(train_df)
    
    # 4. Split entrenamiento/validación dentro del 70%
    val_split_idx = int(len(X_train) * (1 - VAL_SPLIT / TRAIN_SPLIT))
    
    X_train_final = X_train[:val_split_idx]
    y_train_final = y_train[:val_split_idx]
    X_val = X_train[val_split_idx:]
    y_val = y_train[val_split_idx:]
    
    print(f"\n📊 Split entrenamiento/validación:")
    print(f"   🏋️  Train final: {len(X_train_final)} muestras")
    print(f"   ✅ Validación:  {len(X_val)} muestras")
    
    # 5. Entrenar modelo
    model, train_acc, val_acc = train_model(X_train_final, y_train_final, X_val, y_val)
    
    # 6. Guardar modelo XGBoost
    model.save_model(str(MODEL_XGB_PATH))
    print(f"\n💾 Modelo XGBoost guardado: {MODEL_XGB_PATH}")
    
    # 7. Exportar a ONNX
    export_to_onnx(model, MODEL_ONNX_PATH)
    
    # 8. Guardar scaler
    scaler = save_scaler(X_train_final, SCALER_PATH)
    
    # 9. Guardar metadatos
    save_features_meta(FEATURES_META_PATH)
    
    # 10. Preparar datos de backtesting (el 30% no visto)
    print("\n🔧 Preparando datos de backtesting...")
    X_test, y_test, test_features = prepare_training_data(test_df)
    
    # 11. Evaluar en datos no vistos
    if len(X_test) > 0:
        X_test_scaled = scaler.transform(X_test)
        test_acc = model.score(X_test_scaled, y_test)
        print(f"\n🎯 Precisión en datos NO VISTOS (30% final): {test_acc*100:.2f}%")
    
    # 12. Test de inferencia ONNX
    test_inference(MODEL_ONNX_PATH, SCALER_PATH, X_test if len(X_test) > 0 else X_train)
    
    # 13. Resumen final
    print("\n" + "=" * 70)
    print("✅ ENTRENAMIENTO COMPLETADO")
    print("=" * 70)
    print(f"\n📦 Modelos generados:")
    print(f"   • {MODEL_ONNX_PATH}")
    print(f"   • {MODEL_XGB_PATH}")
    print(f"   • {SCALER_PATH}")
    print(f"   • {FEATURES_META_PATH}")
    print(f"\n📊 Métricas:")
    print(f"   • Precisión entrenamiento: {train_acc*100:.2f}%")
    print(f"   • Precisión validación:    {val_acc*100:.2f}%")
    if len(X_test) > 0:
        print(f"   • Precisión backtesting:   {test_acc*100:.2f}%")
    print(f"\n🚀 Para ejecutar backtesting completo:")
    print(f"   python run_full_backtest.py")
    print("=" * 70)
    
    return model


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Entrenar modelo ONNX con datos históricos reales")
    parser.add_argument('--symbols', nargs='+', 
                        help='Símbolos para entrenar (default: todos los descargados)')
    
    args = parser.parse_args()
    
    main(symbols=args.symbols)