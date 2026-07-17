# AUDITORÍA COMPLETA — CIP-Lite (Consolidación de Módulos Duplicados)

Fecha: 2026-07-16
Objetivo: Detectar módulos repetidos con funciones iguales y dejar UN único módulo
profesional por responsabilidad (backtest, estrategias, etc.). Eliminar lo muerto;
crear lo necesario y adaptativo (cualquier símbolo, temporalidad y estrategia).

## 1. Inventario de capas de módulos (estructura duplicada)

| Capa | Estado | Uso real |
|------|--------|----------|
| `01_data_ingestion/` … `09_brain_cline/` | VIVO | Usado por `main.py` vía `importlib` |
| `src/modules/` (9 subcarpetas) | MUERTO | 0 imports en todo el repo (`grep "from src.modules"` → 0) |
| `05_backtesting_engine/` | STUB | Solo `__init__.py` |
| `src/modules/backtesting_engine/` | STUB | No existe el archivo |
| `services/` | VIVO | Capa de servicios canónica usada por `run_full_backtest.py`, `main.py`, tests |

**Decisión:** Eliminar `src/modules/` completo y los stubs de backtesting vacíos.
La capa `services/` es el canonical; `01-09` se conserva porque `main.py` la usa.

## 2. Backtesting — 3+ implementaciones duplicadas

| Archivo | Rol | Decisión |
|---------|-----|----------|
| `services/backtesting/engine.py` (+ walk_forward, monte_carlo, out_of_sample, visualizer, capacity_turnover) | Motor profesional REAL | CONSERVAR (canonical) |
| `run_full_backtest.py` | Orquestador sobre `services/backtesting` | CONSERVAR + refactorizar a runner genérico |
| `backtest_profesional_cline.py` | Duplicado con datos sintéticos hardcodeados | ELIMINAR (migrar `ONNXRegimeStrategy` a `services/strategies/`) |
| `cline_master.py` | Entrypoint que importa el anterior | ELIMINAR |
| `scripts/backtest_15m_strategies.py` | Motor `BT15m` duplicado | ELIMINAR |
| `scripts/backtest_15m_signalexit.py` | Motor `Backtest15mSignalExit` duplicado | ELIMINAR |
| `scripts/backtest_15m_trend.py` | Variante duplicada | ELIMINAR |
| `scripts/backtest_15m_widestop.py` | Variante duplicada | ELIMINAR |
| `scripts/backtest_walkforward_15m.py` | Motor `BacktestWalkforward15m` duplicado | ELIMINAR |
| `scripts/backtest_walkforward_v6.py` | Variante duplicada | ELIMINAR |
| `scripts/backtest_15m_sweep.py` | Útil (tuning de params) | MIGRAR a `scripts/tune_backtest.py` sobre motor único |

## 3. Estrategias — 7+ implementaciones

| Archivo | Estrategias | Uso | Decisión |
|---------|-------------|-----|----------|
| `services/strategies/base_strategy.py` | `BaseStrategy` ABC + `StrategyRegistry` | VIVO (canonical) | CONSERVAR |
| `services/strategies/enhanced_strategies.py` | MeanReversion, Momentum, Breakout, MarketMaking, Sentiment, Ensemble | VIVO | CONSERVAR |
| `services/ml/advanced_strategy.py` | `AdvancedTradingStrategy` | Solo `tests/test_ml.py` | ELIMINAR + migrar test |
| `services/ml/improved_strategy.py` | `ImprovedTrendStrategy` | Solo `tests/test_ml.py` | ELIMINAR + migrar test |
| `services/ml/predictor.py` | FeatureEngineering/XGBoost/EnsemblePredictor | Solo `tests/test_ml.py` | ELIMINAR + migrar test |
| `services/ml/enhanced_strategy.py` | `EnhancedTradingStrategy` | 0 imports | ELIMINAR |
| `services/ml/institutional_strategy.py` | `InstitutionalTradingStrategy` | 0 imports | ELIMINAR |
| `services/ml/optimized_predictor.py` | `OptimizedStrategy` | 0 imports | ELIMINAR |
| `services/ml/optimized_strategy_v2.py` | `OptimizedStrategyV2` | 0 imports | ELIMINAR |
| `backtest_profesional_cline.py` (`ONNXRegimeStrategy`) | Régimen ONNX | Duplicado | MIGRAR a `services/strategies/onnx_regime_strategy.py` |

**Decisión:** `services/strategies/` es el único lugar para estrategias.
Se crea `services/strategies/onnx_regime_strategy.py` (registrable) para no perder
la capacidad ONNX. Los tests de ML se redirigen a `services/backtesting/engine.py`
y `services/strategies/` (que ya existen y son estables).

## 4. Backtest profesional único y adaptativo (resultado)

`run_full_backtest.py` queda como ÚNICO runner:

    python run_full_backtest.py --symbols BTC ETH SOL --timeframe 15m \
        --strategy momentum --quick

- `--symbols`: cualquiera (carga parquet por `SYMBOL_TIMEFRAME.parquet`).
- `--timeframe`: 1m/5m/15m/1h/4h/D… (define archivo de datos).
- `--strategy`: nombre registrado en `StrategyRegistry` (momentum, mean_reversion,
  breakout, sentiment_contrarian, onnx_regime, ensemble…).
- Mantiene Walk-Forward, Out-of-Sample, Monte Carlo, reporte HTML.

## 5. Checklist de ejecución

- [x] Auditoría documentada
- [x] Eliminar `src/modules/`
- [x] Eliminar stubs `05_backtesting_engine/`, `src/modules/backtesting_engine/`
- [x] Eliminar `services/ml/*` duplicados (6 archivos)
- [x] Eliminar 7 scripts `backtest_15m_*` / `backtest_walkforward_*`
- [x] Migrar `ONNXRegimeStrategy` a `services/strategies/onnx_regime_strategy.py`
- [x] Refactorizar `run_full_backtest.py` a runner genérico (símbolo/tf/estrategia)
- [x] Eliminar `backtest_profesional_cline.py` y `cline_master.py`
- [x] Migrar `tests/test_ml.py` a módulos vivos
- [x] Crear `scripts/tune_backtest.py` (tuning sobre motor único)
- [x] `py_compile` + `pytest` de validación