#!/usr/bin/env python3
"""
🧠 CLINE MASTER - Sistema Unificado de Trading
Punto de entrada único para backtest, paper trading y live trading
Con permisos administrativos completos para Cline
"""

import sys
sys.path.insert(0, '/home/javier/Público/proyectos desarrollo/bot-institucional-qwen-trae/cip-lite')

import argparse
import asyncio
from datetime import datetime

from services.cline_trading_bot import create_cline_bot
from services.admin.access_control import setup_admin_access, PermissionLevel
from backtest_profesional_cline import run_backtest as run_backtest_core


def print_banner():
    print("=" * 70)
    print("🧠 CLINE MASTER - Sistema Unificado de Trading Institucional")
    print("=" * 70)
    print(f"   Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)


def cmd_backtest(args):
    """Ejecutar backtest profesional"""
    print("\n📊 MODO BACKTEST")
    print(f"   Símbolos: {args.symbols}")
    print(f"   Fuente: {args.source}")
    print(f"   Capital: ${args.capital:,.2f}")

    trades, final_capital = run_backtest_core(
        symbols=args.symbols,
        data_source=args.source
    )

    print("\n" + "=" * 70)
    print("📈 RESULTADOS BACKTEST")
    print("=" * 70)
    print(f"\n💎 Trades: {len(trades)}")
    if trades:
        wins = sum(1 for t in trades if t['pnl_pct'] > 0)
        print(f"🏆 Wins: {wins} | Losses: {len(trades) - wins}")
        print(f"📈 Win Rate: {wins / len(trades) * 100:.1f}%")
        print(f"💰 Capital Final: ${final_capital:,.2f}")
        print(f"🚀 Retorno: {(final_capital / args.capital - 1) * 100:.2f}%")

    print("\n✅ Backtest finalizado!")


def cmd_paper_trading(args):
    """Ejecutar paper trading con Cline"""
    print("\n📝 MODO PAPER TRADING")
    print(f"   Símbolos: {args.symbols}")
    print(f"   Capital: ${args.capital:,.2f}")
    print(f"   Intervalo: {args.interval}s")

    bot = create_cline_bot(
        initial_capital=args.capital,
        admin_mode=False
    )

    access = setup_admin_access(bot, role='paper_trader')

    print(f"\n✅ Bot configurado: Paper Trading")
    print(f"   Rol: {access.get_current_role().name}")
    print(f"   Permisos: {sum(bot.permissions.values())}/{len(bot.permissions)}")

    try:
        asyncio.run(bot.run_continuous(
            symbols=args.symbols,
            data_source=args.source,
            interval_seconds=args.interval
        ))
    except KeyboardInterrupt:
        print("\n\n⏹️  Paper trading detenido")
        print(f"   Trades totales: {bot.state.total_trades}")
        print(f"   PnL diario: ${bot.state.daily_pnl:,.2f}")


def cmd_live_trading(args):
    """Ejecutar trading en vivo con Cline (requiere permisos admin)"""
    print("\n💰 MODO LIVE TRADING")
    print(f"   Símbolos: {args.symbols}")
    print(f"   Capital: ${args.capital:,.2f}")
    print(f"   Intervalo: {args.interval}s")

    if not args.admin:
        print("\n❌ ERROR: Live trading requiere permisos administrativos")
        print("   Usa --admin para otorgar permisos")
        return

    bot = create_cline_bot(
        initial_capital=args.capital,
        admin_mode=True
    )

    access = setup_admin_access(bot, role='admin' if not args.super_admin else 'super_admin')

    print(f"\n⚠️  ADVERTENCIA: Live Trading Activo")
    print(f"   Rol: {access.get_current_role().name}")
    print(f"   Permisos: {sum(bot.permissions.values())}/{len(bot.permissions)}")
    print(f"   Capital: ${args.capital:,.2f}")

    if args.super_admin:
        print("\n🚨 MODO SUPER ADMIN - Acceso total concedido")

    confirm = input("\n¿Confirmas que quieres operar con dinero real? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Operación cancelada por el usuario")
        return

    if args.api_key and args.api_secret:
        print("\n🔑 Configurando API keys...")
        bot.exchange = type('Exchange', (), {})()

    try:
        asyncio.run(bot.run_continuous(
            symbols=args.symbols,
            data_source=args.source,
            interval_seconds=args.interval
        ))
    except KeyboardInterrupt:
        print("\n\n⏹️  Live trading detenido")

        if args.emergency_on_exit:
            print("\n🚨 Ejecutando emergency stop...")
            asyncio.run(bot.emergency_stop_all())


def cmd_emergency_stop(args):
    """Detener todas las operaciones"""
    print("\n🚨 EMERGENCY STOP")

    bot = create_cline_bot(initial_capital=10000.0, admin_mode=True)
    access = setup_admin_access(bot, role='admin')

    print("   Ejecutando emergency stop...")

    result = asyncio.run(bot.emergency_stop_all())

    if result.get('status') == 'EMERGENCY_COMPLETE':
        print(f"   ✅ Posiciones cerradas: {result.get('closed', 0)}")
    else:
        print(f"   ❌ Error: {result.get('reason', 'Desconocido')}")


def cmd_analyze(args):
    """Analizar mercado sin operar"""
    print(f"\n📊 ANÁLISIS DE MERCADO: {args.symbol}")
    print(f"   Fuente: {args.source}")

    bot = create_cline_bot(initial_capital=10000.0, admin_mode=False)
    access = setup_admin_access(bot, role='read_only')

    from backtest_profesional_cline import generate_synthetic_data, fetch_ccxt_data

    df = None
    if args.source == 'ccxt':
        df = fetch_ccxt_data(args.symbol)
    if df is None:
        base_prices = {
            'BTC/USDT': 50000,
            'ETH/USDT': 3000,
            'SOL/USDT': 100,
            'ADA/USDT': 0.4
        }
        base = base_prices.get(args.symbol, 100)
        df = generate_synthetic_data(base, n=1000)

    analysis = bot.brain.analyze_market(df, args.symbol.replace('/USDT', ''))
    signal = bot.brain.generate_trading_decision(df, args.symbol.replace('/USDT', ''))

    print("\n📋 ANÁLISIS:")
    print(f"   Precio: ${analysis.price:,.2f}")
    print(f"   Tendencia: {analysis.trend}")
    print(f"   Volatilidad: {analysis.volatility:.2%}")
    print(f"   Volumen: {analysis.volume_profile}")

    print("\n🎯 SEÑAL:")
    print(f"   Dirección: {signal.signal}")
    print(f"   Confianza: {signal.confidence:.1%}")
    print(f"   Stop Loss: ${signal.stop_loss:,.2f}")
    print(f"   Take Profit: ${signal.take_profit:,.2f}")

    print("\n✅ Análisis completado")


def main():
    parser = argparse.ArgumentParser(
        description='🧠 Cline Master - Sistema Unificado de Trading'
    )

    subparsers = parser.add_subparsers(dest='command', help='Comandos disponibles')

    bt = subparsers.add_parser('backtest', help='Ejecutar backtest profesional')
    bt.add_argument('--symbols', nargs='+', default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT'])
    bt.add_argument('--source', choices=['synthetic', 'ccxt', 'mt5'], default='synthetic')
    bt.add_argument('--capital', type=float, default=10000.0)

    pt = subparsers.add_parser('paper', help='Paper trading (simulado)')
    pt.add_argument('--symbols', nargs='+', default=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'])
    pt.add_argument('--source', choices=['synthetic', 'ccxt', 'mt5'], default='synthetic')
    pt.add_argument('--capital', type=float, default=10000.0)
    pt.add_argument('--interval', type=int, default=60)

    lt = subparsers.add_parser('live', help='Live trading (dinero real)')
    lt.add_argument('--symbols', nargs='+', default=['BTC/USDT', 'ETH/USDT'])
    lt.add_argument('--source', choices=['synthetic', 'ccxt', 'mt5'], default='ccxt')
    lt.add_argument('--capital', type=float, default=10000.0)
    lt.add_argument('--interval', type=int, default=60)
    lt.add_argument('--admin', action='store_true', help='Habilitar modo admin')
    lt.add_argument('--super-admin', action='store_true', help='Modo super admin')
    lt.add_argument('--api-key', help='API key del exchange')
    lt.add_argument('--api-secret', help='API secret del exchange')
    lt.add_argument('--emergency-on-exit', action='store_true', help='Emergency stop al salir')

    subparsers.add_parser('emergency', help='Emergency stop - cerrar todas las posiciones')

    ana = subparsers.add_parser('analyze', help='Analizar mercado sin operar')
    ana.add_argument('--symbol', required=True, help='Símbolo a analizar (ej: BTC/USDT)')
    ana.add_argument('--source', choices=['synthetic', 'ccxt'], default='synthetic')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    print_banner()

    if args.command == 'backtest':
        cmd_backtest(args)
    elif args.command == 'paper':
        cmd_paper_trading(args)
    elif args.command == 'live':
        cmd_live_trading(args)
    elif args.command == 'emergency':
        cmd_emergency_stop(args)
    elif args.command == 'analyze':
        cmd_analyze(args)


if __name__ == "__main__":
    main()