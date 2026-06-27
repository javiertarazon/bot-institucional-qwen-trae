#!/usr/bin/env python3
"""
Aura-X Daily Intelligence Report Generator
Genera DAILY_INTEL.md que Trae/Kiro leerá para ajustar config.json

Ejecutar cada noche a las 23:00 UTC (cierre NY)
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, Counter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


# Rutas del proyecto (asume ejecución desde cip-lite/)
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "data" / "trades.db"
OUTPUT_PATH = PROJECT_ROOT / "DAILY_INTEL.md"
CONFIG_PATH = PROJECT_ROOT / "config.json"


def init_db():
    """Inicializa la base de datos SQLite si no existe."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL,
            exit_price REAL,
            lot_size REAL,
            pnl_usd REAL,
            pnl_points REAL,
            duration_seconds INTEGER,
            regime TEXT,
            rsi_at_entry REAL,
            atr_at_entry REAL,
            spread_at_entry REAL,
            candle_body_pct REAL,
            hour_utc INTEGER,
            exit_reason TEXT,
            sl_distance REAL,
            tp_distance REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol)')
    conn.commit()
    return conn


def get_today_trades(conn):
    """Obtiene todas las operaciones del día actual"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = conn.execute(
        "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY timestamp",
        (f"{today}%",)
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def analyze_trades(trades):
    """Análisis estadístico completo por activo"""
    if not trades:
        return {}

    analysis = {}
    by_symbol = defaultdict(list)
    for t in trades:
        by_symbol[t['symbol']].append(t)

    for symbol, sym_trades in by_symbol.items():
        wins = [t for t in sym_trades if t['pnl_usd'] > 0]
        losses = [t for t in sym_trades if t['pnl_usd'] <= 0]

        # Métricas generales
        total = len(sym_trades)
        win_rate = len(wins) / total * 100 if total > 0 else 0
        net_pnl = sum(t['pnl_usd'] for t in sym_trades)

        avg_win = sum(t['pnl_usd'] for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t['pnl_usd'] for t in losses) / len(losses) if losses else 0

        # Profit Factor
        gross_profit = sum(t['pnl_usd'] for t in wins)
        gross_loss = abs(sum(t['pnl_usd'] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        analysis[symbol] = {
            'total': total,
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': win_rate,
            'net_pnl': net_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'win_conditions': analyze_conditions(wins) if wins else {},
            'loss_conditions': analyze_conditions(losses) if losses else {},
        }

    return analysis


def analyze_conditions(trade_list):
    """Analiza las condiciones de entrada de un grupo de trades"""
    if not trade_list:
        return {}

    return {
        'avg_candle_body': sum(t.get('candle_body_pct', 0) or 0 for t in trade_list) / len(trade_list),
        'avg_rsi': sum(t.get('rsi_at_entry', 50) or 50 for t in trade_list) / len(trade_list),
        'avg_atr': sum(t.get('atr_at_entry', 0) or 0 for t in trade_list) / len(trade_list),
        'avg_spread': sum(t.get('spread_at_entry', 0) or 0 for t in trade_list) / len(trade_list),
        'hours': [t.get('hour_utc', 0) for t in trade_list if t.get('hour_utc') is not None],
        'regimes': [t.get('regime', 'UNKNOWN') for t in trade_list],
        'exit_reasons': [t.get('exit_reason', 'unknown') for t in trade_list],
    }


def find_patterns(analysis):
    """Detecta patrones accionables para Trae"""
    patterns = {'winners': [], 'losers': [], 'management': []}

    for symbol, data in analysis.items():
        if data['total'] == 0:
            continue

        # === PATRONES GANADORES ===
        wc = data['win_conditions']
        if data['win_rate'] > 55 and wc.get('avg_candle_body', 0) > 50:
            patterns['winners'].append(
                f"**{symbol}**: Win Rate {data['win_rate']:.0f}% con velas de cuerpo >{wc['avg_candle_body']:.0f}%. "
                f"Optimizar para capturar más tendencia."
            )

        if wc.get('hours'):
            top_hours = Counter(wc['hours']).most_common(3)
            hours_str = ", ".join([f"{h}:00" for h, _ in top_hours])
            patterns['winners'].append(f"**{symbol}**: Horas más rentables: {hours_str}")

        # === PATRONES PERDEDORES ===
        lc = data['loss_conditions']
        if data['losses'] > 0:
            if lc.get('avg_spread', 0) > 35:
                patterns['losers'].append(
                    f"**{symbol}**: Spread promedio en pérdidas: {lc['avg_spread']:.1f} points. "
                    f"REDUCIR max_spread."
                )

            if lc.get('hours'):
                loss_hours = Counter(lc['hours']).most_common(2)
                hours_str = ", ".join([f"{h}:00" for h, _ in loss_hours])
                patterns['losers'].append(
                    f"**{symbol}**: Horas con más pérdidas: {hours_str}. "
                    f"CONSIDERAR añadir a blacklist_hours_utc."
                )

            if lc.get('avg_candle_body', 100) < 30:
                patterns['losers'].append(
                    f"**{symbol}**: Pérdidas con velas débiles (cuerpo <{lc['avg_candle_body']:.0f}%). "
                    f"AUMENTAR min_candle_body_percent."
                )

        # === GESTIÓN ===
        exit_reasons = wc.get('exit_reasons', [])
        if exit_reasons:
            tp_count = sum(1 for r in exit_reasons if r == 'TP_HIT')
            trailing_count = sum(1 for r in exit_reasons if r == 'TRAILING')

            if trailing_count > 0:
                patterns['management'].append(
                    f"**{symbol}**: Trailing stop capturó {trailing_count} operaciones. "
                    f"Configuración funcionando bien."
                )

            if data['profit_factor'] > 1.5:
                patterns['management'].append(
                    f"**{symbol}**: Profit Factor = {data['profit_factor']:.2f}. "
                    f"Estrategia rentable - mantener parámetros."
                )
            elif data['profit_factor'] < 1.0 and data['total'] > 5:
                patterns['management'].append(
                    f"**{symbol}**: Profit Factor = {data['profit_factor']:.2f} < 1.0. "
                    f"REVISAR parámetros urgentemente."
                )

    return patterns


def generate_trae_actions(patterns, current_config):
    """Genera acciones específicas para Trae"""
    actions = []

    # Acciones por patrones perdedores
    for pattern in patterns['losers']:
        if 'blacklist_hours' in pattern.lower() or 'horas con más pérdidas' in pattern.lower():
            actions.append("Revisar y actualizar `blacklist_hours_utc` en el activo correspondiente.")
        if 'spread' in pattern.lower():
            actions.append("Reducir `max_spread_pips` o `max_spread_points` según corresponda.")
        if 'vela' in pattern.lower() or 'cuerpo' in pattern.lower():
            actions.append("Aumentar `min_candle_body_percent` para filtrar velas de indecisión.")

    # Acciones por patrones ganadores
    for pattern in patterns['winners']:
        if 'tendencia' in pattern.lower() or 'capturar más' in pattern.lower():
            actions.append("Considerar ampliar `base_tp_pips` o activar trailing más temprano.")

    # Acciones por gestión
    for pattern in patterns['management']:
        if 'urgentemente' in pattern.lower():
            actions.append("⚠️ URGENTE: Revisar y ajustar parámetros - Profit Factor < 1.0")
        elif 'mantener' in pattern.lower():
            actions.append("Mantener configuración actual (rendimiento óptimo).")

    if not actions:
        actions.append("No se requieren cambios significativos. Mantener configuración.")

    return actions


def generate_report(trades, analysis, patterns, actions):
    """Genera el reporte Markdown"""
    today = datetime.utcnow().strftime("%d %b %Y")
    timestamp = datetime.utcnow().isoformat() + "Z"

    total_trades = len(trades)
    total_wins = sum(1 for t in trades if t['pnl_usd'] > 0)
    total_pnl = sum(t['pnl_usd'] for t in trades)
    symbols = list(set(t['symbol'] for t in trades)) if trades else []

    report = f"""# REPORTE DIARIO DE INTELIGENCIA - {today}

> **Generado:** {timestamp}
> **Para:** Agente Trae/Kiro - Cerebro de Evolución del Sistema Aura-X
> **Propósito:** Analizar operaciones del día y sugerir ajustes a `config.json`

---

## 📊 RESUMEN EJECUTIVO

| Métrica | Valor |
|---------|-------|
| **Total Operaciones** | {total_trades} |
| **Ganadas** | {total_wins} ({(total_wins/total_trades*100) if total_trades else 0:.1f}%) |
| **P&L Neto** | ${total_pnl:+.2f} USD |
| **Activos Operados** | {', '.join(symbols) if symbols else 'Ninguno'} |

---

"""

    # Análisis por activo
    if analysis:
        report += "## 📈 ANÁLISIS POR ACTIVO\n\n"
        for symbol, data in analysis.items():
            report += f"""### {symbol}
- **Operaciones:** {data['total']} | **W/L:** {data['wins']}/{data['losses']} | **WR:** {data['win_rate']:.1f}%
- **P&L:** ${data['net_pnl']:+.2f} | **Profit Factor:** {data['profit_factor']:.2f}
- **Avg Win:** ${data['avg_win']:+.2f} | **Avg Loss:** ${data['avg_loss']:+.2f}

"""
    else:
        report += "## 📈 ANÁLISIS POR ACTIVO\n\nNo se operó hoy o no hay datos suficientes.\n\n"

    # Patrones ganadores
    report += "## 🟢 PATRONES GANADORES (A PROVECHAR)\n\n"
    if patterns['winners']:
        for p in patterns['winners']:
            report += f"- {p}\n"
    else:
        report += "- No se detectaron patrones ganadores significativos.\n"
    report += "\n"

    # Patrones perdedores
    report += "## 🔴 PATRONES PERDEDORES (A EVITAR)\n\n"
    if patterns['losers']:
        for p in patterns['losers']:
            report += f"- {p}\n"
    else:
        report += "- No se detectaron patrones perdedores significativos.\n"
    report += "\n"

    # Gestión
    report += "## 🟡 OPTIMIZACIONES DE GESTIÓN\n\n"
    if patterns['management']:
        for p in patterns['management']:
            report += f"- {p}\n"
    else:
        report += "- Gestión dentro de parámetros normales.\n"
    report += "\n"

    # Acciones para Trae
    report += """---

## 🎯 ACCIONES PARA TRAE (MODIFICAR `config.json`)

**⚠️ REGLAS INQUEBRANTABLES - NO VIOLAR:**
- NO modificar `max_open_trades` (debe permanecer en 3)
- NO modificar `risk_per_trade_percent` (debe permanecer en 0.20)
- NO modificar `max_trades_per_asset` (debe permanecer en 2)
- Solo modificar valores numéricos en secciones permitidas

**ACCIONES ESPECÍFICAS:**

"""
    for i, action in enumerate(actions, 1):
        report += f"{i}. {action}\n"

    report += f"""
---

## 📋 RESUMEN DE CONFIGURACIÓN ACTUAL

"""
    # Incluir resumen de config actual
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r') as f:
                cfg = json.load(f)
            report += f"- **Versión:** {cfg.get('version', 'N/A')}\n"
            report += f"- **Capital:** ${cfg.get('global_settings', {}).get('account_balance_usd', 'N/A')}\n"
            report += f"- **Riesgo/trade:** {cfg.get('global_settings', {}).get('risk_per_trade_percent', 'N/A')}%\n"
            report += f"- **Max trades:** {cfg.get('global_settings', {}).get('max_open_trades', 'N/A')}\n"
        else:
            report += "- ⚠️ config.json no encontrado. Crear archivo base.\n"
    except Exception as e:
        report += f"- ⚠️ Error leyendo config: {e}\n"

    report += f"""
---

*Reporte generado automáticamente por Aura-X Intelligence Engine*
*Próxima ejecución programada: 23:00 UTC*
"""

    return report


def main():
    """Función principal"""
    logger.info("🧠 [Aura-X Intelligence] Iniciando generación de reporte diario...")

    try:
        conn = init_db()
        trades = get_today_trades(conn)

        if not trades:
            logger.warning("⚠️ No hay operaciones registradas hoy")
            report = f"""# REPORTE DIARIO DE INTELIGENCIA - {datetime.utcnow().strftime('%d %b %Y')}

## 📊 RESUMEN
- No se registraron operaciones hoy.
- El sistema puede haber estado en pausa o el mercado no presentó condiciones válidas.

## 🎯 ACCIONES PARA TRAE
1. Revisar si los filtros en `config.json` son demasiado restrictivos.
2. Verificar que la conexión al broker esté activa.
3. Considerar reducir `min_candle_body_percent` si es necesario.
"""
        else:
            logger.info(f"📊 Analizando {len(trades)} operaciones del día...")
            analysis = analyze_trades(trades)
            patterns = find_patterns(analysis)

            # Cargar config actual
            current_config = {}
            if CONFIG_PATH.exists():
                try:
                    with open(CONFIG_PATH, 'r') as f:
                        current_config = json.load(f)
                except Exception:
                    pass

            actions = generate_trae_actions(patterns, current_config)
            report = generate_report(trades, analysis, patterns, actions)

        # Guardar reporte
        OUTPUT_PATH.write_text(report, encoding='utf-8')

        logger.info(f"✅ Reporte generado: {OUTPUT_PATH}")
        logger.info(f"📊 {len(trades)} operaciones analizadas")
        logger.info(f"📁 Tamaño del reporte: {OUTPUT_PATH.stat().st_size} bytes")

        conn.close()

    except Exception as e:
        logger.error(f"❌ Error generando reporte: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
