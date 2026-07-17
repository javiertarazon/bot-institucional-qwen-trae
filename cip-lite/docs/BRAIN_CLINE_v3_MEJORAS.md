# 🧠 Brain Cline v3.0 - Documentación de Mejoras

> **Rama:** `feature/brain-cline-v3`
> **Fecha:** Julio 2026
> **Versión:** 3.0.0

---

## 📋 Resumen de Cambios

Se implementaron **15 mejoras** en el módulo Brain Cline, elevando la capacidad de análisis técnico y toma de decisiones del sistema de trading algorítmico CIP-Lite.

### Archivos Modificados

| Archivo | Versión Anterior | Versión Nueva |
|---------|-----------------|---------------|
| `cip-lite/09_brain_cline/brain.py` | v2.0 | v3.0 |
| `cip-lite/src/modules/brain_cline/brain.py` | v2.0 | v3.0 (sync) |
| `cip-lite/08_orchestrator/orchestrator.py` | v2.0 | v2.1 |

---

## 🆕 Mejoras Implementadas

### 1. TechnicalAnalysisEngine
**Archivo:** `brain.py` - Clase `TechnicalAnalysisEngine`

Motor de análisis técnico que genera un snapshot completo del mercado en una sola llamada:

- **Indicadores calculados:** RSI, MACD (línea + señal), ADX, Bollinger Bands (posición -1 a 1)
- **Soportes/Resistencias dinámicos:** Basados en swing highs/lows con ventana de 20 períodos
- **Volatilidad:** Clasificada en HIGH/MEDIUM/LOW con valor numérico
- **Manejo de errores:** Snapshot fallback con valores por defecto si algo falla

```python
snapshot = tech_engine.get_technical_snapshot(df, "EURUSD")
# snapshot.rsi, snapshot.adx, snapshot.bb_position, snapshot.support, etc.
```

### 2. RegimeClassifier Mejorado
**Archivo:** `brain.py` - Clase `RegimeClassifier`

Clasificación de régimen de mercado con 4 métodos combinados:

| Método | Peso | Descripción |
|--------|------|-------------|
| ONNX | 50% | Clasificador ML si el modelo está disponible |
| Volatilidad | 30% | Ratio high/low promedio |
| EMA Alignment | 35% | Cruce y pendiente de EMAs 9/21 |
| Impulso | 25% | Tamaño de cuerpo de velas |

**Regímenes detectables:** MOMENTUM, LATERAL, VOLATILE, TRENDING_UP, TRENDING_DOWN, HIGH_IMPULSE, LOW_LIQUIDITY

```python
regime, confidence = regime_classifier.classify(df)
stability = regime_classifier.get_regime_stability(window=10)
```

### 3. MemoryConsultant
**Archivo:** `brain.py` - Clase `MemoryConsultant`

Integración con Signal Memory para aprendizaje adaptativo:

- **Pesos adaptativos:** Ajusta pesos de indicadores según correlaciones históricas
- **Override de decisiones:** Bloquea operaciones si hay 3+ pérdidas consecutivas o win rate < 30%
- **Cache inteligente:** TTL de 1 hora para evitar consultas repetitivas
- **Pesos por defecto:** Optimizados para cada régimen (momentum, lateral, volátil)

```python
weights = memory.get_adaptive_weights("EURUSD", "TRENDING_UP")
override = memory.should_override_decision("EURUSD", "BUY", 0.8)
```

### 4. Análisis Multi-timeframe
**Archivo:** `brain.py` - Método `_analyze_multi_frame()`

Analiza 3 timeframes simultáneamente:

| Timeframe | Ventana | Propósito |
|-----------|---------|-----------|
| Corto (TF1) | 5 velas | Momentum inmediato |
| Medio (TF2) | 20 velas | Tendencia de sesión |
| Largo (TF3) | 50 velas | Tendencia general |

**Output:** Tendencia general + score de coherencia (0.0-1.0)

```python
mrf = brain._analyze_multi_frame(df)
# mrf['overall_trend'], mrf['coherence'], mrf['coherent']
```

### 5. Detección de Divergencias
**Archivo:** `brain.py` - Método `_detect_divergence()`

Detecta divergencias entre precio y RSI:

- **Bullish:** Precio hace mínimo más bajo, RSI hace mínimo más alto
- **Bearish:** Precio hace máximo más alto, RSI hace máximo más bajo
- **Requisito:** Mínimo 30 velas de datos

```python
divergence = tech_engine._detect_divergence(close)
# "BULLISH", "BEARISH", o "NONE"
```

### 6. Patrones de Velas
**Archivo:** `brain.py` - Método `_detect_candle_pattern()`

Reconoce 8 patrones de velas en los últimos 3 candles:

| Patrón | Señal |
|--------|-------|
| DOJI | Indecisión |
| HAMMER | Posible reversión alcista |
| SHOOTING_STAR | Posible reversión bajista |
| BULLISH_ENGULFING | Reversión alcista fuerte |
| BEARISH_ENGULFING | Reversión bajista fuerte |
| THREE_WHITE_SOLDIERS | Tendencia alcista continuada |
| THREE_BLACK_CROWS | Tendencia bajista continuada |

### 7. Perfil de Volumen
**Archivo:** `brain.py` - Método `_analyze_volume_profile()`

Clasifica el volumen en 5 perfiles:

| Perfil | Condición |
|--------|-----------|
| ACCUMULATION | Vol > 1.3x + precio sube > 0.5% |
| DISTRIBUTION | Vol > 1.3x + precio baja > 0.5% |
| HIGH | Vol > 1.3x |
| LOW | Vol < 0.6x |
| NORMAL | Resto |

### 8. Sistema de Alertas
**Archivo:** `brain.py` - Método `_detect_alerts()`

Genera alertas en 6 categorías:

1. RSI extremo (< 20 o > 80)
2. Volatilidad alta (> 2.5%)
3. Acumulación/Distribución detectada
4. Divergencias alcistas/bajistas
5. Bollinger Band cerca del extremo (> 0.9)
6. Patrones de vela significativos (Engulfing, Hammer, Shooting Star)

### 9. Confianza Mejorada con Entropía
**Archivo:** `brain.py` - Método `_calculate_enhanced_confidence()`

La confianza final considera 7 factores:

| Factor | Peso |
|--------|------|
| Score técnico | 35% |
| Estabilidad del régimen | 15% |
| Coherencia multi-timeframe | 15% |
| Volumen conviction | 10% |
| Fuerza de tendencia (ADX) | 10% |
| Penalización por entropía | -10% |
| Bonus por divergencias | +10% |

**Entropía:** Detecta señales contradictorias (ej: RSI sobrecompra + MACD positivo)

### 10. Pesos Adaptativos por Régimen
**Archivo:** `brain.py` - Método `_default_weights()`

| Indicador | Momentum | Trending Down | Volátil | Lateral |
|-----------|----------|---------------|---------|---------|
| RSI | 0.8 | 1.0 | 1.0 | 1.0 |
| MACD | 1.0 | 0.9 | 0.5 | 0.4 |
| ADX | 1.0 | 0.8 | 0.3 | 0.2 |
| Volumen | 0.7 | 0.8 | 0.6 | 0.5 |
| Bollinger | 0.5 | 0.6 | 1.0 | 0.8 |

### 11. SL/TP Dinámicos con ATR
**Archivo:** `brain.py` - Método `_calculate_trade_levels()`

- **Stop Loss:** Mínimo entre soporte y 2 ATRs (cap 3%)
- **Take Profit:** Máximo entre resistencia y 3 ATRs
- **Risk/Reward:** Calculado automáticamente (cap 5:1)

### 12. Decisión Multi-factor
**Archivo:** `brain.py` - Método `_decide_signal()`

Sistema de scoring con 5 condiciones para compra y 5 para venta:

**Condiciones de COMPRA:**
1. Tendencia alcista + score técnico > 0.6 (peso 2)
2. Régimen favorable (MOMENTUM, TRENDING_UP) (peso 2)
3. Divergencia alcista (peso 2)
4. RSI sobreventa en tendencia alcista (peso 1)
5. Volumen alto o acumulación (peso 1)

**Condiciones de VENTA:**
1. Tendencia bajista + score técnico > 0.6 (peso 2)
2. Régimen bajista (MOMENTUM, TRENDING_DOWN) (peso 2)
3. Divergencia bajista (peso 2)
4. RSI sobrecompra en tendencia bajista (peso 1)
5. Volumen alto o distribución (peso 1+)

### 13. Performance Summary
**Archivo:** `brain.py` - Método `get_performance_summary()`

```python
{
    'total_analyses': 150,
    'total_decisions': 45,
    'buy_signals': 12,
    'sell_signals': 8,
    'hold_signals': 25,
    'avg_confidence': 0.65,
    'regime_distribution': {'TRENDING_UP': 80, 'LATERAL': 70},
    'onnx_available': True,
    'version': '3.0.0'
}
```

### 14. Regime History
**Archivo:** `brain.py` - Método `get_regime_history()`

```python
[
    {'timestamp': '2026-07-13T10:30:00', 'regime': 'TRENDING_UP', 'confidence': 0.85},
    {'timestamp': '2026-07-13T10:31:00', 'regime': 'TRENDING_UP', 'confidence': 0.82},
]
```

### 15. Orchestrator v2.1
**Archivo:** `orchestrator.py`

- TradingContext con 10+ campos nuevos
- Integración directa con MemoryConsultant
- Logs detallados con régimen, divergencia y urgencia
- `get_performance_summary()` para monitoreo
- `_ensure_brain_columns()` para compatibilidad de DataFrames

---

## 🔧 Requisitos Técnicos

### Dependencias
```txt
pandas>=1.3.0
numpy>=1.21.0
structlog>=20.0.0
# Opcional (para clasificación ONNX):
onnxruntime>=1.10.0
```

### Compatibilidad
- Python 3.8+
- Compatible con módulos existentes (01-08)
- No rompe la API pública existente

### Tests
```bash
# Test de imports
python -c "from src.modules.brain_cline.brain import Brain; print(Brain().get_performance_summary()['version'])"

# Test end-to-end
python -c "
import pandas as pd, numpy as np
from src.modules.brain_cline.brain import Brain
df = pd.DataFrame({'close': np.random.randn(100).cumsum() + 1.08, 'high': 1.09, 'low': 1.08, 'volume': 10000})
brain = Brain()
analysis = brain.analyze_market(df, 'EURUSD')
decision = brain.generate_trading_decision(df, 'EURUSD')
print(f'Tendencia: {analysis.trend}, Señal: {decision.signal.value}')
"
```

---

## 📊 Impacto en el Sistema

| Métrica | Antes (v2.0) | Después (v3.0) |
|---------|--------------|----------------|
| Indicadores analizados | 3 (RSI, MACD, SMA) | 8+ (RSI, MACD, ADX, BB, volumen, divergencias, patrones) |
| Factores de decisión | 2 (tendencia + confianza) | 10+ (técnico, régimen, divergencia, volumen, multi-TF, entropía) |
| Precisión de régimen | 1 método (ONNX o reglas) | 4 métodos combinados |
| Alertas | 0 | 6 tipos |
| Integración con memoria | Ninguna | Pesos adaptativos + override |
| SL/TP | Fijos (1.5 R:R) | Dinámicos (ATR + SR) |

---

## 🚀 Uso

```python
from brain import Brain

# Instancia singleton
brain = Brain()

# Análisis completo
analysis = brain.analyze_market(df, "EURUSD")
print(f"Tendencia: {analysis.trend}")
print(f"Régimen: {analysis.regime}")
print(f"Confianza: {analysis.confidence:.2%}")

# Decisión de trading
decision = brain.generate_trading_decision(df, "EURUSD")
print(f"Señal: {decision.signal.value}")
print(f"SL: {decision.stop_loss:.5f}")
print(f"TP: {decision.take_profit:.5f}")

# Contexto para orquestador
context = brain.get_market_context("EURUSD")

# Resumen de rendimiento
perf = brain.get_performance_summary()
```

---

## ✅ Estado de la Integración

- [x] Brain Cline v3.0 implementado
- [x] Sincronizado con `src/modules/brain_cline/brain.py`
- [x] Orchestrator v2.1 actualizado
- [x] Tests de importación exitosos
- [x] Test end-to-end con datos sintéticos exitoso
- [x] Compatibilidad hacia atrás mantenida
- [ ] Entrenar modelo ONNX para producción (`python_brain/train_and_export_onnx.py`)
- [ ] Tests unitarios formales