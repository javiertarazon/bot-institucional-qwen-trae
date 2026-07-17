# 📋 Requisitos - CIP Lite v2.0 Enterprise Modules

## Funcionalidades Implementadas

### 1. Strategy ABC Interface
- **BaseStrategy** abstract class con contracto común
- **StrategySignal** dataclass con metadata completa
- **StrategyRegistry** para gestión de estrategias
- Compatibilidad con el patrón Strategy para extensibilidad

### 2. Backtesting Engine
- Profit Factor calculado automáticamente
- Tracking de rachas (win/loss streaks)
- Cataologación de condiciones de operaciones ganadoras/perdedoras
- Métricas: Sharpe, Sortino, Max DD, Win Rate, Total Return

### 3. Admin Dashboard (Streamlit)
- Autenticación con token HMAC
- 6 tabs: Overview, Backtesting, Paper Trading, Risk, ML Signals, Metrics
- Control de emergency stop
- Visualización de métricas en tiempo real

### 4. ML Integration (ONNX)
- Regime detection: MOMENTUM vs LATERAL
- Latencia < 1ms en CPU
- Fallback automático si modelo no disponible
- Features: RSI Delta, ATR Ratio, EMA Distance, Candle Body %

### 5. Prometheus Metrics
- `cip_pnl_usd` - Profit & Loss
- `cip_roi_percent` - ROI porcentual
- `cip_win_rate` - Tasa de aciertos
- `cip_profit_factor` - Ratio de beneficio
- `cip_max_drawdown` - Drawdown máximo
- `cip_trades_total{status}` - Contador de operaciones
- `cip_current_win_streak` / `cip_current_loss_streak` - Rachas actuales
- `cip_trade_conditions{outcome}` - Histograma de condiciones

---

## Requisitos Técnicos

### Python Version
- Python 3.12+ (recomendado)

### Dependencias
```txt
pandas>=2.0
numpy>=1.24
prometheus-client>=0.20
onnxruntime>=1.16
streamlit>=1.35
psutil>=5.9
structlog>=24.0
```

### Hardware Recomendado
- CPU: i5 o superior
- RAM: 8GB mínimo
- Docker: Para Prometheus/Grafana

---

## Seguridad

### Autenticación
- Token JWT/HMAC para admin dashboard
- Variables de entorno: `ADMIN_TOKEN`
- Roles: read_only, paper_trading, live_trading, admin, super_admin

### Infraestructura
- Redis para caché
- DuckDB para feature store
- Prometheus para métricas
- Grafana para dashboards

---

## Métricas de Calidad

### Cobertura de Tests Objetivo
- Risk Manager: 90%
- Cline Brain: 85%
- Backtesting: 80%
- UI: 70% (manual testing)

### Latencias
- ONNX Inference: < 1ms
- Backtest (100 días): < 5s
- API Response: < 100ms