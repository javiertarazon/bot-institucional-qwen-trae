#!/usr/bin/env python3
"""
📋 RUN PAPER TRADING - CIP v2.0
Inicia el motor de paper trading que simula operaciones en vivo
como si fueran reales, usando datos CCXT en tiempo real.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import argparse
from pathlib import Path
from datetime import datetime

from services.papertrading.engine import PaperTradingEngine, run_paper_trading_loop

# ==================== CONFIGURACIÓN ====================
DEFAULT_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT",
    "DOGE/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT",
]

DEFAULT_INTERVAL = 3600  # 1 hora (velas de 1h)
DEFAULT_CAPITAL = 10000.0


def main():
    parser = argparse.ArgumentParser(description="Paper Trading CIP v2.0")
    parser.add_argument('--symbols', nargs='+', default=DEFAULT_SYMBOLS[:3],
                        help='Símbolos a operar (default: BTC ETH SOL)')
    parser.add_argument('--capital', type=float, default=DEFAULT_CAPITAL,
                        help=f'Capital inicial (default: ${DEFAULT_CAPITAL:,.0f})')
    parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL,
                        help=f'Intervalo entre ciclos en segundos (default: {DEFAULT_INTERVAL})')
    parser.add_argument('--cycles', type=int, default=None,
                        help='Máximo de ciclos (default: infinito)')
    parser.add_argument('--all', action='store_true',
                        help='Operar las 10 criptos top')
    parser.add_argument('--quick', action='store_true',
                        help='Modo rápido: intervalo de 60s para pruebas')
    
    args = parser.parse_args()
    
    # Determinar símbolos
    if args.all:
        symbols = DEFAULT_SYMBOLS
    else:
        symbols = args.symbols
    
    interval = 60 if args.quick else args.interval
    
    print("=" * 70)
    print("📋 CIP - PAPER TRADING v2.0")
    print("   Simulación de operaciones en vivo como si fueran reales")
    print("=" * 70)
    
    print(f"\n📋 Configuración:")
    print(f"   Símbolos: {len(symbols)}")
    for s in symbols:
        print(f"      • {s}")
    print(f"   Capital inicial: ${args.capital:,.2f}")
    print(f"   Intervalo: {interval}s ({interval/60:.1f} min)")
    print(f"   Máx ciclos: {args.cycles or '∞'}")
    print(f"   Fuente datos: Binance (CCXT) - Solo lectura")
    
    # Verificar modelo ONNX
    model_path = Path(__file__).parent / "models" / "regime_model.onnx"
    if not model_path.exists():
        print(f"\n⚠️  Modelo ONNX no encontrado en {model_path}")
        print(f"   El sistema usará estrategia basada solo en indicadores técnicos")
        print(f"   Para entrenar el modelo: python python_brain/train_and_export_onnx.py")
    
    print(f"\n🚀 Iniciando paper trading...")
    print(f"   Presiona Ctrl+C para detener")
    
    # Crear engine
    engine = PaperTradingEngine(
        initial_capital=args.capital,
        symbols=symbols,
    )
    
    # Ejecutar bucle
    try:
        asyncio.run(run_paper_trading_loop(
            engine,
            interval_seconds=interval,
            max_cycles=args.cycles,
        ))
    except KeyboardInterrupt:
        print("\n\n⚠️  Paper trading detenido por el usuario")
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Paper trading finalizado")


if __name__ == "__main__":
    main()