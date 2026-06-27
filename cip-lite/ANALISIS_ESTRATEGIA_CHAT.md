# ANÁLISIS Y PLAN DE ACCIÓN - PROYECTO CIP-LITE
## Bot Trader Institucional - Estrategia del Chat Exportado

**Fecha:** 2026-06-27
**Analista:** Asistente Técnico Especializado - Trader Institucional

---

## I. RESUMEN EJECUTIVO DEL ESTADO ACTUAL

### A. Hallazgos del Proyecto cip-lite

El proyecto **cip-lite v0.3.0** se encuentra en un estado **funcional pero con oportunidades críticas de mejora**. A continuación, el diagnóstico:

| Área | Estado | Observaciones |
|------|--------|---------------|
| **Estructura base** | ✅ Sólida | 100+ archivos, módulos bien organizados |
| **Backtesting engine** | ⚠️ Funcional con problemas | Resultados negativos en multi-activo |
| **ML/Predictor** | ✅ Implementado | XGBoost + scaler funcional |
| **MT5 Integration** | ✅ Robusto | Shadow mode + fallback para Linux |
| **Tests** | ⚠️ Cobertura baja (~11%) | 9/9 tests principales pasan |
| **Documentación** | ✅ Completa | FASE 1-5 documentadas |
| **Fast Path (Rust)** | ✅ Operativo | RSS ingestion funcional |
| **Estrategia XAUUSD** | ❌ No implementada | Estrategia general crypto, no específica para oro |

### B. Resultados del Backtest Multi-Activo (Actual)

```
═══════════════════════════════════════════════════
MÉTRICAS CRÍTICAS DEL BACKTEST ACTUAL
═══════════════════════════════════════════════════
Bitcoin (BTC):   -1.16% retorno, 0% win rate ❌
Solana (SOL):    -0.40% retorno, 54.55% win rate ⚠️
Oro (XAU/USD):   +0.18% retorno, 50% win rate ⚠️
EUR/USD:         +0.18% retorno, 50% win rate ⚠️

Sharpe Promedio:  -4.95 (MUY MALO)
Drawdown Promedio: -1.04%
Outperformance:  -2.95% vs Buy & Hold

DIAGNÓSTICO: La estrategia actual NO ES RENTABLE.
Necesita reingeniería completa para XAUUSD/EURUSD.
```

---

## II. ANÁLISIS DE ERRORES Y MALAS PRÁCTICAS DETECTADAS

### A. Errores Críticos en Estrategia Actual

#### 1. **Stop Loss y Take Profit Inadecuados (3%/6%)**
- **Problema:** SL=3% y TP=6% en XAUUSD significa movimientos de $70 y $140 respectivamente en oro ($2,300).
- **Impacto:** INCOMPATIBLE con scalping M1. Estos son parámetros para swing trading.
- **Solución del chat:** SL=10 pips, TP=12 pips (ajustado para $500 = $1 riesgo/trade).

#### 2. **Sin Clasificación de Régimen de Mercado**
- **Problema:** La estrategia opera igual en lateral, volátil y momentum.
- **Impacto:** Muere por mecha en mercados laterales (sobre-operación sin dirección).
- **Solución del chat:** MRC (Market Regime Classifier) con 3 estados + estrategia específica.

#### 3. **Sin Límite de Operaciones Concurrentes**
- **Problema:** Puede abrir operaciones ilimitadas en backtest.
- **Impacto:** En live, puede sobreexponer la cuenta.
- **Solución del chat:** HARD-CODED máximo 3 operaciones en Rust atómico.

#### 4. **Sin Gestión de Riesgo Dinámica por Volatilidad**
- **Problema:** Lotaje fijo basado en capital, ignora ATR.
- **Impacto:** En NFP o CPI, el riesgo en $ se dispara.
- **Solución del chat:** Kelly fraccional ajustado por ATR, reducción por pérdidas consecutivas.

### B. Malas Prácticas de Código Detectadas

| Archivo | Problema | Severidad |
|---------|----------|-----------|
| `services/backtesting/engine.py` | Generación de datos sintéticos sin validación de régimen | Media |
| `services/ml/predictor.py` | Sin validación cruzada walk-forward | Alta |
| `services/mt5_integration.py` | Fallback que oculta errores en producción | Media |
| `tests/test_mt5_system.py` | Mocks sin simular latencia/slippage real | Media |
| `services/execution/engine.py` | RiskManager sin verificación de correlación | Alta |

### C. Faltantes Críticos Identificados

1. **Estrategia específica para XAUUSD** con lógica SMC/ICT
2. **Estrategia específica para EURUSD** M1 scalping
3. **Market Regime Classifier** (MRC) funcional
4. **Motor Rust de Riesgo** con hot-reload de config.json
5. **Sistema de archivos Trae** (.trae/rules.md) para auto-mejora
6. **Generador de Daily Intel** para análisis post-sesión
7. **Conector cTrader Open API** nativo para Linux

---

## III. PLAN DE ACCIÓN ESTRATÉGICO

### Fase 1: CORRECCIONES INMEDIATAS (Prioridad Alta)

#### 1.1 Corregir Estrategia Mejorada (`improved_strategy.py`)
- [ ] Reducir SL/TP para scalping (10/12 pips en lugar de 3%/6%)
- [ ] Implementar ATR-based stop loss dinámico
- [ ] Agregar filtro de cuerpo de vela mínimo (>40%)

#### 1.2 Implementar MRC (`market_regime_classifier.py`)
- [ ] Crear clasificador XGBoost ligero (3 estados)
- [ ] Validar con walk-forward
- [ ] Exportar a ONNX para inferencia rápida

#### 1.3 Crear Estrategias por Activo
- [ ] `strategy_xauusd.py` - Momentum + Smart Money
- [ ] `strategy_eurusd.py` - Mean Reversion + Breakout

### Fase 2: MOTOR DE RIESGO INSTITUCIONAL (Prioridad Alta)

#### 2.1 Rust Core Multi-Activo
- [ ] Refactorizar `fast-path/src/main.rs` para cálculo de riesgo
- [ ] Implementar hot-reload de config.json cada 10s
- [ ] Límites atómicos: global=3, por_activo=2

#### 2.2 Sistema de Configuración Dinámica
- [ ] Crear `config.json` multi-activo balanceado
- [ ] Implementar validación JSON automática
- [ ] Sistema de versionado Git para auditoría

### Fase 3: CONECTOR BROKER NATIVO LINUX (Prioridad Media)

#### 3.1 cTrader Open API
- [ ] Instalar `ctrader-open-api` library
- [ ] Implementar `ctrader_connector.py` con failover
- [ ] Validar latencia <5ms

#### 3.2 MetaAPI como Respaldo
- [ ] Mantener MetaAPI como fallback
- [ ] Auto-detección de mejor ruta

### Fase 4: AUTO-MEJORA CON TRAE (Prioridad Media)

#### 4.1 Sistema Daily Intel
- [ ] Crear `generate_daily_intel.py`
- [ ] Schema de SQLite para diario de trading
- [ ] Generación de `DAILY_INTEL.md` estructurado

#### 4.2 Reglas para Trae
- [ ] Crear `.trae/rules.md` con prompt maestro
- [ ] Definir acciones permitidas en `config.json`
- [ ] Whitelist/blacklist de modificaciones

### Fase 5: VALIDACIÓN Y TESTING (Prioridad Alta)

#### 5.1 Backtesting Específico XAUUSD
- [ ] Obtener datos históricos reales (1 año M1)
- [ ] Comparar vs benchmark (Buy & Hold)
- [ ] Validar Profit Factor > 1.5

#### 5.2 Paper Trading Forward
- [ ] 14 días de paper trading con Pepperstone Demo
- [ ] Validar slippage y spread reales
- [ ] Métricas: Sharpe > 1.5, Max DD < 6%

---

## IV. IMPLEMENTACIÓN RECOMENDADA (Orden de Ejecución)

### Paso 1: Crear Estructura Aura-X (Inmediato)
```bash
mkdir -p ~/aura-x-trader/{rust_core/src,python_brain,.trae,data,logs}
```

### Paso 2: Implementar Estrategia Específica XAUUSD
- Archivo: `services/strategies/xauusd_scalper.py`
- Lógica: SMC + Liquidity Sweep + FVG
- Timeframe: M1

### Paso 3: Implementar MRC
- Archivo: `services/ml/market_regime_classifier.py`
- Modelo: XGBoost exportado a ONNX
- Features: RSI delta, ATR ratio, EMA distance, candle body

### Paso 4: Motor de Riesgo Rust
- Archivo: `rust_core/src/main.rs`
- Endpoints: TCP socket puerto 8080
- Filtros: 7 niveles (spread, horario, RSI, volatilidad, etc.)

### Paso 5: Generador Daily Intel
- Archivo: `python_brain/generate_daily_intel.py`
- Output: `DAILY_INTEL.md` estructurado

### Paso 6: Conector cTrader
- Archivo: `python_brain/ctrader_connector.py`
- Latencia objetivo: <5ms

---

## V. MÉTRICAS DE ÉXITO (KPIs)

| Métrica | Objetivo Mínimo | Objetivo Óptimo |
|---------|-----------------|-----------------|
| Win Rate | > 55% | > 65% |
| Profit Factor | > 1.5 | > 2.0 |
| Sharpe Ratio | > 1.5 | > 2.5 |
| Max Drawdown | < 10% | < 6% |
| Expectancy/trade | > 0.3R | > 0.5R |
| Latencia ejecución | < 100ms | < 30ms |
| Uptime | > 95% | > 99% |

---

## VI. PRÓXIMOS PASOS INMEDIATOS

1. **Verificar entorno:** Python 3.10+, Rust 1.70+, dependencias instaladas
2. **Generar datos históricos XAUUSD M1** de los últimos 2 años
3. **Crear `config.json` balanceado** para $500 USD
4. **Implementar MRC básico** (RandomForest fallback mientras se entrena ONNX)
5. **Compilar motor Rust** con hot-reload
6. **Paper trading** 14 días en Pepperstone Demo

---

## VII. RECOMENDACIONES CRÍTICAS PARA EL USUARIO

### Seguridad
1. **CAMBIAR CONTRASEÑA de Exness** (fue compartida en chat)
2. Usar `.env` con `python-dotenv` para credenciales
3. Nunca hardcodear credenciales en código

### Broker
- **Primario:** Pepperstone cTrader (latencia <5ms, nativo Linux)
- **Respaldo:** Exness vía MetaAPI
- **Capital inicial:** $500 USD Standard

### Perfil de Riesgo
- **Modo:** BALANCED
- **Riesgo/trade:** 0.20% ($1.00 USD)
- **Máx operaciones:** 3 simultáneas
- **Drawdown kill:** -5% diario → pausa 24h

### Hardware
- **Target:** Zorin OS, i5 6ta Gen, 20GB RAM
- **Consumo objetivo:** < 100MB RAM total
- **CPU objetivo:** < 10% en pico

---

**Conclusión:** El proyecto cip-lite tiene una base sólida pero necesita reingeniería específica para XAUUSD/EURUSD con la estrategia de scalping institucional definida en el chat exportado. La implementación es viable en 4-6 semanas siguiendo el plan propuesto.

*Fin del Análisis*
