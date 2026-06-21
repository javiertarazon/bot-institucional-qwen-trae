# Documentación del Sistema de Análisis Institucional

## Resumen

Este sistema implementa cuatro componentes clave para el análisis institucional de estrategias de trading:

1. **Walk-Forward Analysis**: Análisis de ventanas móviles para evitar data leakage
2. **Simulaciones Monte Carlo**: Generación de escenarios de mercado para pruebas de estrés
3. **Pruebas Out-of-Sample**: Validación rigurosa en datos no utilizados para entrenamiento
4. **Capacidad de Capital y Turnover**: Análisis de capacidad de despliegue y costos de transacción

---

## 1. Walk-Forward Analysis

### Descripción
El análisis Walk-Forward permite evaluar estrategias reentrenando el modelo en ventanas móviles de tiempo, evitando el data leakage que ocurre en los backtests estáticos.

### Uso
```python
from services.backtesting import WalkForwardAnalysis, WalkForwardConfig

# Configurar
config = WalkForwardConfig(
    train_window_days=252,    # 1 año de entrenamiento
    test_window_days=63,      # 3 meses de prueba
    step_days=21,             # 1 mes de paso entre ventanas
    initial_capital=100000.0,
    commission_rate=0.001,
    slippage_pct=0.0005,
    max_position_pct=0.1
)

# Ejecutar
wf = WalkForwardAnalysis(config)
results = wf.run(data, strategy)

# Exportar reporte
wf.export_report('reports/walk_forward.csv')
```

### Reportes Generados
- `walk_forward_report.csv`: Rendimiento por cada ventana

---

## 2. Simulaciones Monte Carlo

### Descripción
Genera múltiples escenarios de mercado basados en datos históricos para probar la robustez de la estrategia.

### Uso
```python
from services.backtesting import MonteCarloSimulator, MonteCarloConfig

# Configurar
config = MonteCarloConfig(
    num_scenarios=10000,      # Número de escenarios
    num_days=252,             # Días por escenario
    initial_price=50000.0,
    parallel=True,            # Ejecución paralela
    num_workers=4
)

# Ejecutar
mc = MonteCarloSimulator(config)
results = mc.run(data, strategy)

# Exportar escenarios
mc.export_scenarios('reports/monte_carlo.csv')
```

### Reportes Generados
- `monte_carlo_scenarios.csv`: Muestra de escenarios simulados
- Resultados del análisis: VaR, CVaR, percentiles, etc.

---

## 3. Pruebas Out-of-Sample

### Descripción
Divide los datos en conjuntos de entrenamiento y prueba, y evalúa la estrategia en:
- Conjuntos de prueba independientes
- Diferentes regímenes de mercado (bull, bear, alta volatilidad, normal)
- Pruebas estadísticas Diebold-Mariano

### Uso
```python
from services.backtesting import OutOfSampleTester, OutOfSampleConfig

# Configurar
config = OutOfSampleConfig(
    test_size_pct=0.3,                            # 30% para prueba
    num_independent_test_sets=3,                  # 3 conjuntos de prueba
    min_return_threshold=0.0,                     # Rendimiento mínimo
    max_drawdown_threshold=-0.2,                  # Drawdown máximo
    significance_level=0.05                       # Nivel de significancia
)

# Ejecutar
oos = OutOfSampleTester(config)
results = oos.run(data, strategy, benchmark_strategy)

# Exportar reportes
oos.export_report('reports/out_of_sample.csv')
```

### Reportes Generados
- `out_of_sample_report_test_sets.csv`: Rendimiento por conjunto de prueba
- `out_of_sample_report_regimes.csv`: Rendimiento por régimen de mercado

---

## 4. Capacidad de Capital y Turnover

### Descripción
Calcula:
- Tamaño máximo de capital que se puede desplegar sin erosionar el rendimiento
- Rotación de la cartera (turnover)
- Costos de transacción asociados

### Uso
```python
from services.backtesting import CapacityTurnoverAnalyzer, CapacityTurnoverConfig

# Configurar
config = CapacityTurnoverConfig(
    base_capital=100000.0,
    max_allowed_slippage_pct=0.01,  # 1% máximo de slippage
    target_return_pct=0.10,          # 10% rendimiento objetivo
    rebalance_frequency_days=21      # Rebalanceo mensual
)

# Ejecutar
ct = CapacityTurnoverAnalyzer(config)
results = ct.run(data, strategy)

# Exportar reportes
ct.export_report('reports/capacity_turnover.csv')
```

### Reportes Generados
- `capacity_turnover_report_turnover.csv`: Métricas de turnover
- `capacity_turnover_report_capacity.csv`: Análisis de capacidad por nivel de capital

---

## Script de Prueba Completo

Se incluye el script `run_institutional_analysis.py` que ejecuta todos los componentes juntos.

Para ejecutarlo:
```bash
cd cip-lite
source venv/bin/activate
python run_institutional_analysis.py
```

---

## Tests

Todos los tests existentes pasaron exitosamente: 130 tests, 0 fallos.
