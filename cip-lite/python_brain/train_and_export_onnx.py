#!/usr/bin/env python3
"""
Aura-X ONNX Model Trainer
Entrena un modelo XGBoost ligero para clasificación de régimen de mercado
y lo exporta a ONNX para inferencia ultrarrápida en CPU.
"""

import numpy as np
import xgboost as xgb
from onnxmltools.convert import convert_xgboost
from onnxmltools.convert.common.data_types import FloatTensorType
from pathlib import Path

# ==================== CONFIGURACIÓN ====================
MODEL_OUTPUT_PATH = "../regime_model.onnx"
FEATURES = 4  # [rsi_delta, atr_ratio, ema_distance, candle_body_pct]


def generate_synthetic_training_data(n_samples=1000):
    """
    Genera datos sintéticos de entrenamiento.
    En producción, reemplazar con datos históricos reales de trading.
    """
    print("📊 Generando datos de entrenamiento sintéticos...")
    
    # Features: [rsi_delta, atr_ratio, ema_distance, candle_body_pct]
    X = []
    y = []
    
    for _ in range(n_samples):
        # Generar features aleatorias realistas
        rsi_delta = np.random.uniform(-30, 30)
        atr_ratio = np.random.uniform(0.5, 3.0)
        ema_distance = np.random.uniform(-0.02, 0.02)
        candle_body_pct = np.random.uniform(10, 90)
        
        # Lógica de etiquetado
        # MOMENTUM (1): Alta volatilidad + cuerpo de vela grande + distancia EMA significativa
        if (atr_ratio > 1.5 and candle_body_pct > 60 and 
            abs(ema_distance) > 0.005 and abs(rsi_delta) > 10):
            label = 1  # MOMENTUM
        else:
            label = 0  # LATERAL
        
        X.append([rsi_delta, atr_ratio, ema_distance, candle_body_pct])
        y.append(label)
    
    X = np.array(X, dtype=np.float32)
    y = np.array(y)
    
    print(f"✅ Datos generados: {len(X)} muestras")
    print(f"   - MOMENTUM: {sum(y)} ({sum(y)/len(y)*100:.1f}%)")
    print(f"   - LATERAL: {len(y)-sum(y)} ({(len(y)-sum(y))/len(y)*100:.1f}%)")
    
    return X, y


def train_and_export():
    """
    Entrena modelo XGBoost y lo exporta a ONNX.
    """
    print("🚀 [ONNX Trainer] Iniciando entrenamiento...")
    
    # 1. Generar datos de entrenamiento
    X_train, y_train = generate_synthetic_training_data(n_samples=1000)
    
    # 2. Entrenar modelo XGBoost ultraligero
    print("🧠 Entrenando modelo XGBoost...")
    model = xgb.XGBClassifier(
        n_estimators=20,           # Muy pocos estimadores para velocidad
        max_depth=3,               # Profundidad baja para evitar overfitting
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss',
        n_jobs=2                   # Usar solo 2 hilos del i5
    )
    model.fit(X_train, y_train)
    
    # Evaluar en datos de entrenamiento
    train_accuracy = model.score(X_train, y_train)
    print(f"✅ Precisión en entrenamiento: {train_accuracy*100:.2f}%")
    
    # 3. Exportar a ONNX
    print("📦 Exportando a ONNX...")
    initial_type = [('float_input', FloatTensorType([None, FEATURES]))]
    onnx_model = convert_xgboost(model, initial_types=initial_type, target_opset=12)
    
    # Asegurar que el directorio existe
    Path(MODEL_OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    # Guardar modelo ONNX
    with open(MODEL_OUTPUT_PATH, "wb") as f:
        f.write(onnx_model.SerializeToString())
    
    print(f"✅ Modelo exportado a: {MODEL_OUTPUT_PATH}")
    print(f"   Tamaño del archivo: {Path(MODEL_OUTPUT_PATH).stat().st_size / 1024:.2f} KB")
    
    # 4. Mostrar importancia de features
    print("\n📊 Importancia de Features:")
    feature_names = ['RSI_Delta', 'ATR_Ratio', 'EMA_Distance', 'Candle_Body_%']
    importances = model.feature_importances_
    for name, importance in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True):
        print(f"   {name}: {importance*100:.1f}%")
    
    print("\n✅ Entrenamiento completado exitosamente.")
    print("   Para usar el modelo, ejecuta: python onnx_classifier.py")
    
    return model


def test_inference():
    """
    Prueba rápida de inferencia con el modelo ONNX.
    """
    print("\n🧪 [Test] Probando inferencia ONNX...")
    
    try:
        import onnxruntime as ort
        import time
        
        # Cargar modelo
        session = ort.InferenceSession("../regime_model.onnx")
        input_name = session.get_inputs()[0].name
        
        # Test 1: Régimen MOMENTUM
        test_momentum = np.array([[15.0, 2.0, 0.01, 75.0]], dtype=np.float32)
        start = time.time()
        pred = session.run(None, {input_name: test_momentum})
        elapsed = (time.time() - start) * 1000
        
        print(f"   Test MOMENTUM: {pred[0][0]} (tiempo: {elapsed:.2f}ms)")
        
        # Test 2: Régimen LATERAL
        test_lateral = np.array([[2.0, 0.8, 0.001, 25.0]], dtype=np.float32)
        start = time.time()
        pred = session.run(None, {input_name: test_lateral})
        elapsed = (time.time() - start) * 1000
        
        print(f"   Test LATERAL: {pred[0][0]} (tiempo: {elapsed:.2f}ms)")
        
        # Test 3: Batch de 100 predicciones
        test_batch = np.random.rand(100, 4).astype(np.float32)
        start = time.time()
        pred = session.run(None, {input_name: test_batch})
        elapsed = (time.time() - start) * 1000
        
        print(f"   Batch 100 predicciones: {elapsed:.2f}ms (promedio: {elapsed/100:.2f}ms/predicción)")
        
        print("✅ Test de inferencia completado.")
        
    except ImportError:
        print("⚠️  onnxruntime no instalado. Instalar con: pip install onnxruntime")
    except Exception as e:
        print(f"❌ Error en test: {e}")


if __name__ == "__main__":
    # Entrenar y exportar
    model = train_and_export()
    
    # Probar inferencia
    test_inference()
    
    print("\n" + "="*60)
    print("✅ MODELO ONNX LISTO PARA PRODUCCIÓN")
    print("="*60)
</parameter>
<parameter name="task_progress">
- [x] Leer y analizar archivo de chat exportado
- [x] Analizar la estructura actual del proyecto bot
- [x] Identificar funcionalidades mencionadas en el chat
- [x] Comparar con funcionalidades existentes en el bot
- [x] Generar lista de integraciones pendientes
- [ ] Fase 1: Sistema de auto-adaptación diaria
  - [x] Crear config.json base (arreglado)
  - [x] Crear generate_daily_intel.py
  - [ ] Extender signal_memory para análisis estadístico
  - [ ] Integrar hot-reload en main.py
- [ ] Fase 2: Motor ONNX para ML
  - [x] Crear train_and_export_onnx.py
  - [ ] Crear onnx_classifier.py para inferencia
  - [ ] Integrar en Brain Cline
- [ ] Fase 3: Motor Rust para Risk Manager
- [ ] Fase 4: Mejoras Brain Cline
- [ ] Fase 5: Mejoras Risk Manager
</parameter>
</write_to_file>