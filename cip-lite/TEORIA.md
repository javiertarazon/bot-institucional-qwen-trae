# 📚 Teoría - CIP Lite v2.0

## Estrategias Implementadas

### 1. Mean Reversion Strategy

**Base Teórica:**
- RSI (Relative Strength Index) para identificar sobrecompra/sobreventa
- Bollinger Bands para definir rangos de precio
- Premisa: Los precios vuelven a la media

**Fórmula RSI:**
```
RSI = 100 - (100 / (1 + RS))
RS = Average Gain / Average Loss
```

**Señales:**
- BUY: RSI < 30 y Precio < BB Lower
- SELL: RSI > 70 y Precio > BB Upper

---

### 2. Momentum Strategy

**Base Teórica:**
- EMA (Exponential Moving Average) para tendencia
- MACD para momentum
- Premisa: Tendencia que se mantiene

**Fórmula MACD:**
```
MACD = EMA(12) - EMA(26)
Signal = EMA(MACD, 9)
Histogram = MACD - Signal
```

**Stops Dinámicos:**
```
Stop = Entry ± (ATR × 2)
ATR = Average True Range (14 periodos)
```

---

### 3. Kelly Criterion (Variable)

**Fórmula:**
```
f* = W - (1-W) / R
Donde:
- f* = fracción óptima del capital
- W = win rate
- R = ratio ganancia/pérdida
```

**Ajuste por volatilidad:**
```
f_ajustado = f* × (1 / (1 + σ × 10))
σ = volatilidad histórica
```

---

## Métricas de Rendimiento

### Profit Factor
```
PF = Σ Ganancias / Σ Pérdidas
PF > 1.0: Estrategia rentable
PF > 2.0: Excelente
```

### Sharpe Ratio
```
S = (R_p - R_f) / σ_p × √252
Donde:
- R_p = retorno de la estrategia
- R_f = tasa libre de riesgo (3%)
- σ_p = volatilidad de la estrategia
```

### Max Drawdown
```
DD = (V_pk - V_min) / V_pk
V_pk = Valor pico del equity
V_min = Valor mínimo posterior
```

### Sortino Ratio
```
Sortino = (R_p - R_f) / σ_downside
Solo considera retorno negativo (más conservador que Sharpe)
```

---

## Detección de Régimen (ONNX)

### Features de Entrada (4):
1. **RSI Delta** - Cambio en momentum
2. **ATR Ratio** - Volatilidad actual vs media
3. **EMA Distance** - Distancia entre medias móviles
4. **Candle Body %** - Fuerza de la vela actual

### Clases:
- **MOMENTUM** - Alta volatilidad, tendencia fuerte
- **LATERAL** - Baja volatilidad, rango estrecho

---

## Gestión de Riesgo

### VaR (Value at Risk)
```
VaR = Capital × σ_portfolio × Z(0.95)
Z(0.95) = 1.65 (percentil 95%)
```

### Correlation Risk
```
Risk = 1 - (n_activos / 10)
Más activos = menor correlación percibida
```

---

## Rachas (Streaks)

### Tracking:
- Se contabilizan operaciones consecutivas ganadoras/perdedoras
- Ayuda a identificar si el sistema está "caliente" o "frío"
- Se usan para pausar operaciones si racha perdedora > threshold

---

## Microestructura (Order Flow)

### CVD (Cumulative Volume Delta):
```
CVD = (Buy Volume - Sell Volume) / Total Volume
Indicador de presión compradora/vendedora
```

### OBI (Order Book Imbalance):
```
OBI = (Bid Depth - Ask Depth) / (Bid Depth + Ask Depth)
Desbalance en el libro de órdenes
```

### Whale Detection:
- Trades en el top 5% por tamaño
- Ratio de volumen de ballenas vs total

---

## Ensemble Strategy

### Consenso:
- Requiere mínimo 2 votos de 3 estrategias
- Pondera confianza promedio
- Reduce falsos positivos

### Weighted Signal:
```
Confidence_final = min(0.95, avg_confidence)
```

---

## Referencias

1. **Kelman, K.** - "Market Regime Detection" (2021)
2. **Schwager, J.D.** - "Trading Systems and Methods" (2020)
3. **Tharp, R.** - "The Definitive Guide to Position Sizing" (2019)
4. **ONNX Runtime Docs** - Microsoft (2024)