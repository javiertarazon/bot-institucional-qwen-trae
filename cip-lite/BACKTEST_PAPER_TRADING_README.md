# 🚀 BACKTESTING + PAPER TRADING - CIP v2.0

Sistema de backtesting profesional con modelo ONNX entrenado con datos reales CCXT y paper trading en vivo.

## 🚀 COMANDOS RÁPIDOS
```bash
cd cip-lite
python main.py --download --years 2          # Descargar datos (10 criptos, 2 años)
python python_brain/train_and_export_onnx.py # Entrenar ONNX (split 70/30)
python main.py --backtest                     # Backtesting completo
python main.py --papertrade --all --capital 10000  # Paper trading en vivo
```

## 🔄 FLUJO SIN SOLAPAMIENTO
- 70% datos → Entrenamiento ONNX (modelo nunca ve el 30% restante)
- 30% datos → Backtesting (datos NO vistos por el modelo)
- Datos en vivo → Paper trading (valida que backtest no está overfitteado)

## 📊 MÉTRICAS
Sharpe, Sortino, Calmar, Win Rate, Profit Factor, Expectancy, Max DD, VaR 95/99%, CVaR, Recovery Factor, Ulcer Index.

## 🧠 ESTRATEGIA ONNX
- MOMENTUM → Tendencia (MA7 vs MA21)
- LATERAL → Mean reversion (Bollinger Bands)

## 📋 PAPER TRADING
- Datos CCXT en tiempo real (solo lectura)
- Comisiones 0.1% + slippage 0.05%
- SL/TP dinámicos + trailing 3%
- Dashboard en consola + SQLite + CSV

*CIP v2.0 - Sistema de Trading Algorítmico Institucional*
