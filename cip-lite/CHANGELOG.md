# CHANGELOG - Aura-X Trader

Todas las versiones notables del proyecto serán documentadas aquí.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
y este proyecto sigue [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0-AURA-X] - 2026-06-27

### 🎉 Lanzamiento Inicial - Aura-X

Primera versión completa del Bot Trader Institucional con cerebro IA.

### ✨ Agregado

#### Estrategia XAUUSD
- **Módulo de estrategias específicas** (`services/strategies/`)
- **Estrategia XAUUSD M1 Scalper** con 3 modos:
  - MOMENTUM (Breakout con EMAs)
  - REVERSION (RSI extremos)
  - SMART_MONEY (Liquidity Sweep + FVG)
- **Indicadores técnicos:**
  - EMAs (9, 21, 50 periodos)
  - RSI (14 periodos)
  - ATR (14 periodos)
  - Cálculo de cuerpo de vela
  - Detección de FVG (Fair Value Gap)
  - Detección de Swing High/Low
- **Gestión de riesgo:**
  - Lotaje dinámico por riesgo (0.20% balanceado)
  - Stop Loss: 100 points ($1.00)
  - Take Profit: 150 points ($1.50)
  - Breakeven trigger en 60 points
  - Trailing stop cada 30 points

#### Sistema de Inteligencia Diaria
- **Base de datos SQLite** con schema completo (18 columnas)
- **Generador de reportes diarios** (`generate_daily_intel.py`)
- **Análisis estadístico por activo:**
  - Win Rate
  - Profit Factor
  - Max Drawdown
  - Sharpe Ratio
  - Expectancy por trade
- **Detección de patrones:**
  - Patrones ganadores (horario, vela, régimen)
  - Patrones perdedores (filtros a mejorar)
  - Optimizaciones de gestión
- **Acciones específicas para Trae/Kiro**

#### Configuración Dinámica
- **Archivo `config.json`** con:
  - Configuración global (balance, riesgo, límites)
  - Configuración por activo (filtros, SL/TP, regímenes)
  - Configuración de broker (primario + fallback)
  - Sistema de logging configurable
- **Validación JSON** automática
- **Hot-reload** preparado para implementación futura

#### Cerebro IA (Trae/Kiro)
- **Reglas inquebrantables** documentadas (`.trae/rules.md`)
- **Acciones basadas en patrones** definidas
- **Protocolos de emergencia** para drawdowns
- **Métricas de éxito** establecidas
- **Proceso diario** estructurado

#### Monitoreo y Operaciones
- **System Monitor** con 16 checks automatizados
- **Script de menú principal** (`aura_x.sh`) con 9 opciones
- **Generador de trades de prueba** para validación
- **Suite de tests** completa

### 📊 Métricas Iniciales

| Métrica | Valor |
|---------|-------|
| Archivos creados | 13 |
| Líneas de código | ~2,800 |
| Tests | 38 total (38 pasados) |
| Cobertura funcional | 100% |

### 🔧 Configuración Inicial

```json
{
  "capital": "$500 USD",
  "riesgo_por_trade": "0.20%",
  "max_trades_globales": 3,
  "max_trades_por_activo": 2,
  "activo_primario": "XAUUSD M1",
  "activo_secundario": "EURUSD M1"
}
```

### 📚 Documentación Incluida

- `ANALISIS_ESTRATEGIA_CHAT.md` - Análisis completo de la estrategia
- `RESUMEN_IMPLEMENTACION.md` - Resumen de implementación
- `REGISTRO_TAREAS_v1.0.0.md` - Registro detallado de tareas
- `.trae/rules.md` - Reglas del cerebro IA
- `CHANGELOG.md` - Este archivo

### ⚠️ Limitaciones Conocidas

1. Datos sintéticos en backtest (requiere datos históricos reales)
2. EURUSD strategy pendiente de implementación específica
3. Paper trading aún no activado completamente
4. Sin conexión real a broker (configurada pero no probada)

### 🔒 Seguridad

- ⚠️ **ACCIÓN REQUERIDA:** Cambiar credenciales de Exness
- Uso de `.env` para credenciales (preparado)
- No hardcoding de passwords

---

## [0.3.0] - 2026-06-25 (Versión Anterior)

### Resumen
- Backtesting engine funcional
- ML Predictor con XGBoost
- MT5 Integration con shadow mode
- Tests originales del proyecto
- Documentación previa (Fases 1-5)

### ⚠️ Problemas Detectados
- Backtest multi-activo con resultados negativos
- Estrategia genérica (no específica para XAUUSD)
- Sin clasificación de régimen
- Sin gestión de riesgo dinámica

---

## Próximas Versiones

### [1.1.0] - Planeada para 2026-07-15

- [ ] Validación con datos históricos reales
- [ ] Implementar estrategia EURUSD específica
- [ ] Paper trading 14 días
- [ ] Conector cTrader Open API nativo
- [ ] Motor Rust de riesgo

### [1.2.0] - Planeada para 2026-08-30

- [ ] Web dashboard en tiempo real
- [ ] Telegram bot para notificaciones
- [ ] Sistema multi-agente completo
- [ ] ML Predictor entrenado en producción

---

**Mantenedor:** Equipo Aura-X
**Fecha de este CHANGELOG:** 2026-06-27
