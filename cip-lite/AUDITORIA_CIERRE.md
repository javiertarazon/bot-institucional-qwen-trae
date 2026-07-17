# CIERRE TÉCNICO — AUDITORÍA Y CONSOLIDACIÓN CIP-Lite

Fecha: 2026-07-16
Estado: COMPLETADO y VALIDADO (18/18 tests pasan, runner end-to-end OK)

## Qué se hizo

### 1. Backtest profesional ÚNICO y adaptativo
- `run_full_backtest.py` refactorizado como runner único:
  `--symbols` (cualquiera), `--timeframe` (1m/5m/15m/1h/4h/D...),
  `--strategy` (nombre registrado). Carga `data/historical/{SYM}_USDT_{TF}.parquet`.
- Mantiene Walk-Forward, Out-of-Sample, Monte Carlo, métricas y reporte HTML.

### 2. Eliminación de duplicados (módulos muertos)
- `src/modules/` (9 subcarpetas): 0 imports en todo el repo → ELIMINADO.
- Stubs `05_backtesting_engine/`, `src/modules/backtesting_engine/`: solo `__init__.py` → ELIMINADOS.
- 7 scripts `scripts/backtest_15m_*` y `backtest_walkforward_*` (cada uno con su
  propio motor duplicado BT15m/Backtest15mSignalExit/BacktestWalkforward15m) → ELIMINADOS.
- `services/ml/`: 6 archivos de estrategia duplicados
  (advanced_strategy, improved_strategy, predictor, enhanced_strategy,
  institutional_strategy, optimized_predictor, optimized_strategy_v2) → ELIMINADOS
  (solo advanced/improved/predictor eran usados por tests; migrados).
- `backtest_profesional_cline.py` y `cline_master.py` (entrypoint duplicado) → ELIMINADOS.

### 3. Consolidación de estrategias en UN lugar
- `services/strategies/` es el único directorio de estrategias.
- `onnx_regime_strategy.py`: migrado desde `backtest_profesional_cline.py`
  (ONNXRegimeStrategy hereda BaseStrategy, compatible con el motor).
- `registry.py`: StrategyRegistry central + StrategyAdapter que traduce
  BaseStrategy→callable del motor y normaliza columnas (Open↔open).
- `enhanced_strategies.py`: ahora heredan de BaseStrategy (name + required_params).

### 4. Tuning unificado
- `scripts/tune_backtest.py`: sweep de (estrategia, riesgo, capital) sobre el
  motor único, sustituye a los 7 scripts eliminados.

### 5. Tests
- `tests/test_ml.py` reescrito para usar módulos vivos
  (services.backtesting.engine + services.strategies).
- pytest + pytest-cov instalados (no existían en el entorno).

## Validación
- `py_compile` de todos los archivos nuevos/modificados: OK.
- `pytest tests/test_ml.py tests/test_backtesting.py`: 18 passed.
- Backtest en vivo: `run_full_backtest.py --symbols BTC --timeframe 15m
  --strategy momentum --quick` completó y generó reports/backtest_report.html
  y reports/backtest_results.json.

## Estructura final (backtest/estrategias)
- Motor: `services/backtesting/{engine,walk_forward,monte_carlo,out_of_sample,visualizer,capacity_turnover}.py`
- Estrategias: `services/strategies/{base_strategy,enhanced_strategies,onnx_regime_strategy,registry}.py`
- Runner: `run_full_backtest.py`
- Tuning: `scripts/tune_backtest.py`
- Capa numérica 01-09 conservada (usada por main.py vía importlib).