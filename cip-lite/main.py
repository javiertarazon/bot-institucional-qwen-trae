#!/usr/bin/env python3
"""
CIP-Lite v2.0 - Sistema de Trading Algorítmico Modular
Punto de entrada principal del sistema
Modos: trading real, backtesting, paper trading
"""

import asyncio
import sys
import json
import time
import os
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Agregar directorios al path
sys.path.insert(0, str(Path(__file__).parent))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger("Main")


def print_banner():
    """Imprime el banner del sistema"""
    print("=" * 70)
    print("🚀 CIP-Lite v2.0 - Crypto Intelligence Platform")
    print("   Trading | Backtesting | Paper Trading | ONNX ML")
    print("=" * 70)


def print_help():
    """Imprime ayuda de uso"""
    print("""
📋 COMANDOS DISPONIBLES:
───────────────────────────────────────────────────────
  python main.py                    → Trading en vivo (predeterminado)
  python main.py --backtest         → Backtesting profesional completo
  python main.py --papertrade       → Paper trading en vivo
  python main.py --download         → Descargar datos históricos CCXT
  
📊 BACKTESTING:
  python main.py --backtest --symbols BTC ETH SOL
  python main.py --backtest --quick
  python main.py --backtest --no-train
  
📋 PAPER TRADING:
  python main.py --papertrade --symbols BTC ETH SOL
  python main.py --papertrade --capital 50000
  python main.py --papertrade --quick  (intervalo 60s)
  python main.py --papertrade --all   (10 criptos)

📥 DESCARGA DE DATOS:
  python main.py --download
  python main.py --download --symbols BTC ETH
  
📈 ENTRENAR MODELO ONNX:
  python python_brain/train_and_export_onnx.py
  python python_brain/train_and_export_onnx.py --symbols BTC ETH
    """)


def main():
    """Función principal con selección de modo"""
    parser = argparse.ArgumentParser(description="CIP-Lite v2.0 - Sistema de Trading")
    parser.add_argument('--backtest', action='store_true', help='Ejecutar backtesting profesional')
    parser.add_argument('--papertrade', action='store_true', help='Ejecutar paper trading')
    parser.add_argument('--download', action='store_true', help='Descargar datos históricos')
    parser.add_argument('--train', action='store_true', help='Entrenar modelo ONNX')
    parser.add_argument('--symbols', nargs='+', help='Símbolos a procesar')
    parser.add_argument('--capital', type=float, default=10000.0, help='Capital inicial')
    parser.add_argument('--quick', action='store_true', help='Modo rápido')
    parser.add_argument('--all', action='store_true', help='Usar todas las 10 criptos')
    parser.add_argument('--no-train', action='store_true', help='No reentrenar modelo ONNX')
    parser.add_argument('--cycles', type=int, help='Máximo de ciclos (paper trading)')
    parser.add_argument('--years', type=int, default=2, help='Años de historia a descargar')
    parser.add_argument('--help-commands', action='store_true', help='Mostrar ayuda de comandos')
    
    args = parser.parse_args()
    
    # Mostrar ayuda si se solicita
    if args.help_commands:
        print_banner()
        print_help()
        return
    
    # Símbolos por defecto (top 10)
    top_10 = [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "ADA/USDT",
        "DOGE/USDT", "DOT/USDT", "AVAX/USDT", "MATIC/USDT", "LINK/USDT",
    ]
    
    # Determinar símbolos
    if args.all:
        symbols = top_10
    elif args.symbols:
        # Normalizar símbolos: añadir /USDT si no tiene par
        symbols = []
        for s in args.symbols:
            if '/' not in s and 'USDT' not in s:
                symbols.append(f"{s}/USDT")
            else:
                symbols.append(s)
    else:
        symbols = None  # Usar default del módulo
    
    # ==================== MODO: DESCARGA DE DATOS ====================
    if args.download:
        print_banner()
        print("\n📥 MODO: DESCARGA DE DATOS HISTÓRICOS")
        print("=" * 70)
        
        import importlib
        downloader = importlib.import_module("01_data_ingestion.historical_downloader")
        
        if symbols is None:
            symbols = downloader.TOP_10_CRYPTOS
        
        print(f"\n⏳ Descargando {len(symbols)} símbolos (últimos {args.years} años)...")
        results = downloader.download_all(years=args.years, symbols=symbols, force=False)
        downloader.print_summary(results)
        return
    
    # ==================== MODO: ENTRENAR MODELO ====================
    if args.train:
        print_banner()
        print("\n🧠 MODO: ENTRENAR MODELO ONNX")
        print("=" * 70)
        
        from python_brain.train_and_export_onnx import main as train_main
        train_main(symbols=symbols)
        return
    
    # ==================== MODO: BACKTESTING ====================
    if args.backtest:
        print_banner()
        print("\n📊 MODO: BACKTESTING PROFESIONAL")
        print("=" * 70)
        
        from run_full_backtest import main as backtest_main
        
        # Pasar argumentos como sys.argv modificado
        sys_args = ['run_full_backtest.py']
        if symbols:
            sys_args.extend(['--symbols'] + symbols)
        if args.quick:
            sys_args.append('--quick')
        if args.no_train:
            sys_args.append('--no-train')
        
        sys.argv = sys_args
        backtest_main()
        return
    
    # ==================== MODO: PAPER TRADING ====================
    if args.papertrade:
        print_banner()
        print("\n📋 MODO: PAPER TRADING")
        print("=" * 70)
        
        from run_paper_trading import main as papertrade_main
        
        if symbols is None:
            symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        
        # Pasar argumentos como sys.argv modificado
        sys_args = ['run_paper_trading.py']
        sys_args.extend(['--symbols'] + symbols)
        sys_args.extend(['--capital', str(args.capital)])
        if args.quick:
            sys_args.extend(['--interval', '60'])
        if args.cycles:
            sys_args.extend(['--cycles', str(args.cycles)])
        if args.all:
            sys_args.append('--all')
        
        sys.argv = sys_args
        papertrade_main()
        return
    
    # ==================== MODO: TRADING EN VIVO (predeterminado) ====================
    print_banner()
    print("\n⚠️  MODO PREDETERMINADO: Trading en vivo no configurado")
    print("   Usa --backtest, --papertrade, --download, o --train")
    print()
    print_help()


if __name__ == "__main__":
    main()