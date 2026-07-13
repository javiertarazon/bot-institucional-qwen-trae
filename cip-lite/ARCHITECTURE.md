# Arquitectura Modular CIP-Lite v2.0
## Sistema de Trading Algorítmico con Cline como Cerebro

---

## 📐 Diseño Modular

### Módulos del Sistema (9 total)

```
cip-lite/
├── 01_data_ingestion/           # Recolección de datos históricos y en vivo
├── 02_indicator_engine/         # Cálculo de indicadores tradicionales y personalizados
├── 03_signal_memory/            # Memoria de operaciones y aprendizaje de patrones
├── 04_data_processor/           # Normalización y conversión a JSON para el cerebro
├── 05_backtesting_engine/       # Backtesting profesional con métricas y gráficas
├── 06_risk_manager/             # Gestión de riesgo auto-ajustable
├── 07_execution_engine/         # Ejecución real (crypto + MT5)
├── 08_orchestrator/             # Coordinador central de todos los módulos
└── 09_brain_cline/              # Cerebro: Integración con Cline para decisiones
```

---

## 🔄 Flujo de Datos entre Módulos

```
[01] Data Sources (CCXT, MT5, RSS)
         ↓
[02] Raw Data → [04] Data Processor → JSON Normalizado
         ↓                                    ↓
[03] Signal Memory ← [05] Backtesting ← [02] Indicator Engine
         ↓                                    ↓
         └──────── [08] Orchestrator ←───────┘
                         ↓
                 [09] Cline Brain (Análisis + Decisiones)
                         ↓
                  [06] Risk Manager (Validación)
                         ↓
                   [07] Execution (Broker)
```

---

## 📦 Descripción de Módulos

### 01. Data Ingestion Module
**Responsabilidad:** Recolectar datos de mercado históricos y en vivo
- **Fuentes:** CCXT (Binance, Coinbase, Kraken, etc.) + MT5 (Forex, Oro, Índices)
- **Tipos de datos:** OHLCV, Order Book, Trades
- **Frecuencias:** 1s, 1m, 5m, 1h, 1d
- **Funciones:**
  - `fetch_historical(symbol, start_date, end_date, timeframe)`
  - `stream_live(symbol, callback)`
  - `get_available_symbols(exchange)`

**Reutiliza:** `services/exchanges/` (Binance, Kraken, Coinbase) + `services/ingestion/`

---

### 02. Indicator Engine Module
**Responsabilidad:** Calcular indicadores técnicos
- **Indicadores tradicionales:**
  - Tendencia: SMA, EMA, WMA, MACD, ADX
  - Volatilidad: ATR, Bollinger Bands, Keltner
  - Momentum: RSI, Stochastics, CCI, Momentum, ROC
  - Volumen: OBV, Volume Profile, MFI
- **Indicadores personalizados:**
  - Combinaciones machine-readable
  - Indicadores basados en patrones de velas
  - Indicadores de liquidez
- **Funciones:**
  - `calculate(symbol, indicator_name, params, df)`
  - `combine(indicators_list, weights)`
  - `generate_signal(df, rule_set)`

**Reutiliza:** Lógica de `services/strategies/enhanced_strategies.py`

---

### 03. Signal Memory Module
**Responsabilidad:** Aprender de operaciones pasadas
- **Almacena:** Todas las operaciones (ganadoras y perdedoras)
- **Analiza:**
  - Patrones ganadores repetitivos
  - Condiciones de pérdida recurrentes
  - Mejores horarios, activos, parámetros
- **Genera:**
  - Reportes diarios/semanales (`DAILY_INTEL.md`)
  - Ajustes de parámetros para configuración
  - Nuevas reglas de filtrado
- **Funciones:**
  - `record_trade(trade_data)`
  - `analyze_performance(period)`
  - `generate_learning_report()`
  - `suggest_parameter_changes()`

**Nuevo:** inspired by `generate_daily_intel.py` del chat

---

### 04. Data Processor Module
**Responsabilidad:** Normalizar datos crudos a formato estándar
- **Transforma:**
  - CCXT format → JSON estándar
  - MT5 format → JSON estándar
  - RSS/Noticias → JSON estructurado
- **Normaliza:**
  - Timestamps a UTC
  - Precios a float
  - Símbolos a formato estándar (EURUSD, XAUUSD)
- **Valida:**
  - Detección de outliers
  - Gaps en datos
  - Integridad de OHLCV
- **Funciones:**
  - `normalize_ccxt(raw_data) → json`
  - `normalize_mt5(raw_data) → json`
  - `validate_ohlcv(df) → bool`

**Nuevo:** Formato unificado para todos los módulos

---

### 05. Backtesting Engine Module
**Responsabilidad:** Probar estrategias históricamente
- **Características:**
  - Walk-forward analysis
  - Out-of-sample testing
  - Monte Carlo simulation
  - Métricas: Sharpe, Sortino, Profit Factor, Max DD, Win Rate
  - Gráficos: Equity curve, Drawdown, Trade distribution
- **Funciones:**
  - `backtest(strategy, data, config) → results`
  - `optimize_parameters(strategy, data, param_grid) → best_params`
  - `generate_report(results) → html/pdf`

**Reutiliza:** `services/backtesting/` completo (engine, visualizer, monte_carlo, walk_forward)

---

### 06. Risk Manager Module
**Responsabilidad:** Gestión de riesgo dinámica y auto-ajustable
- **Características:**
  - Position sizing dinámico (Kelly, ATR-based)
  - Stops dinámicos (ATR, estructurales)
  - Trailing stops inteligentes
  - Límites de exposición por activo y correlación
  - Circuit breakers automáticos
  - VaR diario
- **Ajustes automáticos según:**
  - Volatilidad del mercado
  - Drawdown actual
  - Win rate reciente
  - Capital disponible
- **Funciones:**
  - `calculate_position_size(signal, capital, risk_params) → size`
  - `calculate_stop_loss(entry, df, direction) → price`
  - `check_risk_limits(proposed_trade) → bool`
  - `update_after_trade(result)`

**Reutiliza:** `services/risk/dynamic_risk_manager.py` (mejorar y extender)

---

### 07. Execution Engine Module
**Responsabilidad:** Ejecutar operaciones reales
- **Brokers soportados:**
  - Crypto: Binance, Coinbase, Kraken (vía CCXT)
  - Forex/Oro: MT5, cTrader Open API
- **Operaciones:**
  - Abrir posición (compra/venta)
  - Cerrar posición (market/limit)
  - Modificar stops/take profit
  - Trailing stop en runtime
  - Emergency stop
- **Funciones:**
  - `connect(exchange_name, credentials) → connection`
  - `execute_order(symbol, side, size, sl, tp) → order_result`
  - `close_position(symbol) → result`
  - `modify_position(symbol, new_sl, new_tp) → result`
  - `emergency_stop() → result`

**Reutiliza:** `services/execution/engine.py` + `services/exchanges/`

---

### 08. Orchestrator Module
**Responsabilidad:** Coordinar todos los módulos
- **Flujo principal:**
```
1. Data Ingestion → Obtener datos
2. Indicator Engine → Calcular señales técnicas
3. Signal Memory → Consultar aprendizajes
4. Data Processor → Normalizar para cerebro
5. Cline Brain → Analizar y decidir
6. Risk Manager → Validar riesgo
7. Execution → Ejecutar si procede
8. Signal Memory → Registrar resultado
```
- **Control de flujo:**
  - Manejo de errores y reintentos
  - Timeouts por módulo
  - Logs estructurados
- **Funciones:**
  - `run_cycle(symbols) → results`
  - `run_continuous(symbols, interval) → loop`
  - `emergency_stop() → result`

**Nuevo:** Esqueleto central del sistema

---

### 09. Cline Brain Module
**Responsabilidad:** Cerebro inteligente del sistema
- **Componentes:**
  - Análisis de mercado (tendencia, volatilidad, volumen, sentimiento)
  - Toma de decisiones (ensemble de estrategias)
  - Generación de señales de trading
  - Explicación de decisiones (transparencia)
- **Integración con Cline:**
  - Contexto enriquecido para análisis superior
  - Capacidad de override manual
  - Aprendizaje continuo
- **Funciones:**
  - `analyze_market(df, symbol, sentiment) → analysis`
  - `generate_decision(df, symbol, indicators, memory) → signal`
  - `explain_decision(signal, analysis) → text`
  - `learn_from_outcome(signal, result) → updates`

**Reutiliza:** `services/cline_brain.py` (mejorar/extender)

---

## 🔧 Componentes Transversales

### Configuración
- `config.py` - Configuración global
- `.env` - Credenciales yAPI keys

### Utilidades
- `metrics.py` - Métricas de performance
- `security.py` - Seguridad y cifrado

### Admin
- `admin/access_control.py` - Control de permisos

---

## 📊 Estado de Reutilización

| Componente | Estado | Acción |
|------------|--------|--------|
| Exchanges (Binance, Kraken, Coinbase) | ✅ Listo | Reutilizar |
| Backtesting engine | ✅ Listo | Reutilizar + mejorar |
| Risk Manager | ✅ Listo | Refactorizar y extender |
| Cline Brain | ✅ Listo | Extender |
| Estrategias ML | ✅ Listo | Consolidar |
| RSS Ingestor | ⚠️ Parcial | Mejorar o descartar |
| Feature Store | ⚠️ Parcial | Integrar en Data Processor |
| UI Streamlit | ✅ Listo | Adaptar a nueva arquitectura |

---

## 🎯 Próximos Pasos

1. **Fase 1:** Reestructurar carpetas en módulos
2. **Fase 2:** Refactorizar código existente a nuevos módulos
3. **Fase 3:** Implementar módulos faltantes (Data Processor, Orchestrator)
4. **Fase 4:** Mejorar y extender módulos existentes
5. **Fase 5:** Tests unitarios y de integración
6. **Fase 6:** Documentación completa

---

## 💡 Principios de Diseño

1. **Single Responsibility:** Cada módulo tiene una función clara
2. **Interface Contracts:** Contratos JSON entre módulos
3. **Loose Coupling:** Comunicación vía eventos/mensajes
4. **High Cohesion:** Lógica relacionada en el mismo módulo
5. **Testability:** Cada módulo testeable independientemente
6. **Extensibility:** Fácil agregar nuevos módulos