# REPORTE DIARIO DE INTELIGENCIA - 27 Jun 2026

> **Generado:** 2026-06-27T16:28:48.573811Z
> **Para:** Agente Trae/Kiro - Cerebro de Evolución del Sistema Aura-X
> **Propósito:** Analizar operaciones del día y sugerir ajustes a `config.json`

---

## 📊 RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| **Total Operaciones** | 31 |
| **Ganadas** | 14 (45.2%) |
| **P&L Neto** | $+16.44 USD |
| **Activos Operados** | XAUUSD, EURUSD |

---

## 📈 ANÁLISIS POR ACTIVO

### XAUUSD
- **Operaciones:** 17 | **W/L:** 7/10 | **WR:** 41.2%
- **P&L:** $-0.34 | **Profit Factor:** 0.96
- **Avg Win:** $+1.33 | **Avg Loss:** $-0.97

### EURUSD
- **Operaciones:** 14 | **W/L:** 7/7 | **WR:** 50.0%
- **P&L:** $+16.78 | **Profit Factor:** 1.57
- **Avg Win:** $+6.60 | **Avg Loss:** $-4.20

## 🟢 PATRONES GANADORES (A PROVECHAR)

- **XAUUSD**: Horas más rentables: 15:00, 8:00, 12:00
- **EURUSD**: Horas más rentables: 11:00, 13:00, 9:00

## 🔴 PATRONES PERDEDORES (A EVITAR)

- **XAUUSD**: Horas con más pérdidas: 9:00, 14:00. CONSIDERAR añadir a blacklist_hours_utc.
- **EURUSD**: Horas con más pérdidas: 10:00, 15:00. CONSIDERAR añadir a blacklist_hours_utc.

## 🟡 OPTIMIZACIONES DE GESTIÓN

- **XAUUSD**: Trailing stop capturó 1 operaciones. Configuración funcionando bien.
- **XAUUSD**: Profit Factor = 0.96 < 1.0. REVISAR parámetros urgentemente.
- **EURUSD**: Trailing stop capturó 2 operaciones. Configuración funcionando bien.
- **EURUSD**: Profit Factor = 1.57. Estrategia rentable - mantener parámetros.

---

## 🎯 ACCIONES PARA TRAE (MODIFICAR `config.json`)

**⚠️ REGLAS INQUEBRANTABLES - NO VIOLAR:**
- NO modificar `max_open_trades` (debe permanecer en 3)
- NO modificar `risk_per_trade_percent` (debe permanecer en 0.20)
- NO modificar `max_trades_per_asset` (debe permanecer en 2)
- Solo modificar valores numéricos en secciones permitidas

**ACCIONES ESPECÍFICAS:**

1. Revisar y actualizar `blacklist_hours_utc` en el activo correspondiente.
2. Revisar y actualizar `blacklist_hours_utc` en el activo correspondiente.
3. ⚠️ URGENTE: Revisar y ajustar parámetros - Profit Factor < 1.0
4. Mantener configuración actual (rendimiento óptimo).

---

## 📋 RESUMEN DE CONFIGURACIÓN ACTUAL

- **Versión:** 1.0.0-aura-x
- **Capital:** $500.0
- **Riesgo/trade:** 0.2%
- **Max trades:** 3

---

*Reporte generado automáticamente por Aura-X Intelligence Engine*
*Próxima ejecución programada: 23:00 UTC*
