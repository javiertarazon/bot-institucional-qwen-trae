# 🚀 TRADING MICRO-CUENTAS - Estrategia Rentable

## Objetivo
Crear una estrategia rentable para cuentas pequeñas de $500 con retorno positivo real.

## Resultados Más Prometedores

### `micro_account_scalper.py`
- **Retorno: +4.42%** en cuenta de $500
- **Profit Factor: 4.54** 
- Trades: 79, Wins: 16 (20.3%)
- Mejores trades: +321% ADA, +252% SOL

### `production_v3.py` (mejor win rate)
- **Retorno: +0.94%**
- **Win Rate: 37.8%**
- Profit Factor: 1.74

## Estrategia Recomendada para Paper Trading

```python
# ENTRADA: TREND_PULLBACK
if (close > ema_21 and close < ema_50 and rsi > 35 and rsi < 55):
    entry = close
    sl = close * 0.97    # Stop 3%
    tp = close * 1.12    # TP 12%
    size = 0.20          # 20% position

# TRAILING: Solo después de 5% ganancia
if close > entry * 1.05:
    sl = close * (1 - 0.05)
```

## Ajustes Críticos para Cuentas Pequeñas

1. **Position Sizing**: 20% (no 3%) - acelera el crecimiento
2. **Trailing Agresivo**: 5% después de 5% ganancia (no 3%)
3. **Stop Ancho**: 4% para evitar stops tempranos
4. **TP Ampliado**: 12-15% para capturar movidas grandes

## Archivos Clave
- `data/micro_account_trades.csv` - Trades con retorno positivo
- `final_micro_strategy.py` - Versión final para optimizar
- `docs/BACKTEST_SUMMARY.md` - Análisis completo