#!/usr/bin/env python3
"""
Aura-X Daily Intelligence Report Generator
Genera DAILY_INTEL.md que Trae leerá para ajustar config.json

Este script analiza todas las operaciones del día y genera un reporte
con patrones ganadores/perdedores y acciones específicas de modificación.
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# ==================== CONFIGURACIÓN ====================
DB_PATH = "../data/trading_journal.db"
OUTPUT_PATH = "../DAILY_INTEL.md"
CONFIG_PATH = "../config.json"


def init_db():
    """Inicializa la base de datos si no existe"""
    Path("../data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL NOT NULL,
            lot_size REAL NOT NULL,
            pnl_usd REAL NOT NULL,
            pnl_pips REAL NOT NULL,
            duration_seconds INTEGER NOT NULL,
            regime TEXT,
            rsi_at_entry REAL,
            atr_at_entry REAL,
            spread_at_entry REAL,
            candle_body_pct REAL,
            hour_utc INTEGER,
            exit_reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_trades_date
        ON trades(timestamp)
    """)
    conn.commit()
    return conn


def get_today_trades(conn):
    """Obtiene todas las operaciones del día"""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor = conn.execute(
        "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY timestamp",
        (f"{today}%",)
    )
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def analyze_trades(trades):
    """Análisis estadístico completo por activo"""
    analysis = {}

    # Agrupar por símbolo
    by_symbol = defaultdict(list)
    for t in trades:
        by_symbol[t["symbol"]].append(t)

    for symbol, sym_trades in by_symbol.items():
        wins = [t for t in sym_trades if t["pnl_usd"] > 0]
        losses = [t for t in sym_trades if t["pnl_usd"] <= 0]

        analysis[symbol] = {
            "total": len(sym_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (len(wins) / len(sym_trades) * 100) if sym_trades else 0,
            "net_pnl": sum(t["pnl_usd"] for t in sym_trades),
            "avg_win": (sum(t["pnl_usd"] for t in wins) / len(wins)) if wins else 0,
            "avg_loss": (sum(t["pnl_usd"] for t in losses) / len(losses)) if losses else 0,
            "profit_factor": (
                abs(sum(t["pnl_usd"] for t in wins) / sum(t["pnl_usd"] for t in losses))
                if losses and sum(t["pnl_usd"] for t in losses) != 0
                else float('inf')
            ),
            "win_conditions": {
                "avg_candle_body": (
                    sum(t.get("candle_body_pct", 0) for t in wins) / len(wins)
                    if wins else 0
                ),
                "avg_rsi": (
                    sum(t.get("rsi_at_entry", 50) for t in wins) / len(wins)
                    if wins else 50
                ),
                "avg_atr": (
                    sum(t.get("atr_at_entry", 0) for t in wins) / len(wins)
                    if wins else 0
                ),
                "hours": [t.get("hour_utc", 0) for t in wins],
                "exit_reasons": [t.get("exit_reason", "unknown") for t in wins],
            },
            "loss_conditions": {
                "avg_candle_body": (
                    sum(t.get("candle_body_pct", 0) for t in losses) / len(losses)
                    if losses else 0
                ),
                "avg_rsi": (
                    sum(t.get("rsi_at_entry", 50) for t in losses) / len(losses)
                    if losses else 50
                ),
                "avg_atr": (
                    sum(t.get("atr_at_entry", 0) for t in losses) / len(losses)
                    if losses else 0
                ),
                "hours": [t.get("hour_utc", 0) for t in losses],
                "avg_spread": (
                    sum(t.get("spread_at_entry", 0) for t in losses) / len(losses)
                    if losses else 0
                ),
            }
        }

    return analysis


def find_patterns(analysis):
    """Detecta patrones accionables para Trae"""
    patterns = {"winners": [], "losers": [], "management": []}

    for symbol, data in analysis.items():
        if data["total"] == 0:
            continue

        wc = data["win_conditions"]
        lc = data["loss_conditions"]

        # Patrones ganadores
        if data["win_rate"] > 55 and wc["avg_candle_body"] > 50:
            patterns["winners"].append(
                f"- **{symbol}**: Cuando el cuerpo de vela > {wc['avg_candle_body']:.0f}% "
                f"y RSI ≈ {wc['avg_rsi']:.0f}, la win rate es {data['win_rate']:.0f}%. "
                f"*Considerar trailing stop más agresivo en estas condiciones.*"
            )

        if wc["hours"]:
            from collections import Counter
            top_hours = Counter(wc["hours"]).most_common(3)
            hours_str = ", ".join([f"{h}:00 UTC" for h, _ in top_hours])
            patterns["winners"].append(
                f"- **{symbol}**: Horas más rentables: {hours_str}"
            )

        # Patrones perdedores
        if data["losses"] > 0:
            if lc["avg_spread"] > 1.5:
                patterns["losers"].append(
                    f"- **{symbol}**: El spread promedio en pérdidas fue {lc['avg_spread']:.2f}. "
                    f"*Considerar reducir max_spread en config.json.*"
                )

            if lc["hours"]:
                from collections import Counter
                loss_hours = Counter(lc["hours"]).most_common(3)
                hours_str = ", ".join([f"{h}:00 UTC" for h, _ in loss_hours])
                patterns["losers"].append(
                    f"- **{symbol}**: Horas con más pérdidas: {hours_str}. "
                    f"*Considerar añadir a blacklist_hours_utc.*"
                )

            if lc["avg_candle_body"] < 40:
                patterns["losers"].append(
                    f"- **{symbol}**: Las pérdidas ocurren con velas de cuerpo "
                    f"< {lc['avg_candle_body']:.0f}%. "
                    f"*Considerar subir min_candle_body_percent.*"
                )

        # Gestión de salida
        exit_reasons = wc["exit_reasons"]
        if exit_reasons:
            from collections import Counter
            tp_closes = sum(1 for r in exit_reasons if r == "TP")
            trailing_closes = sum(1 for r in exit_reasons if r == "TRAILING")
            if trailing_closes > tp_closes * 0.5:
                patterns["management"].append(
                    f"- **{symbol}**: El trailing stop capturó {trailing_closes} operaciones. "
                    f"*El trailing está funcionando bien, mantener configuración.*"
                )
            if data["avg_win"] > 0 and data["profit_factor"] > 1.5:
                patterns["management"].append(
                    f"- **{symbol}**: Profit Factor = {data['profit_factor']:.2f}. "
                    f"*Estrategia rentable, considerar aumentar ligeramente el lotaje.*"
                )

    return patterns


def generate_trae_actions(patterns, current_config):
    """Genera acciones específicas para que Trae modifique config.json"""
    actions = []

    for pattern in patterns["losers"]:
        if "blacklist_hours" in pattern:
            actions.append("Revisar y actualizar `blacklist_hours_utc` para el activo mencionado.")
        if "max_spread" in pattern:
            actions.append("Reducir `max_spread_pips` o `max_spread_points` según el activo.")
        if "min_candle_body" in pattern:
            actions.append("Aumentar `min_candle_body_percent` en los filtros del activo.")

    for pattern in patterns["winners"]:
        if "trailing stop" in pattern.lower():
            actions.append("Considerar reducir `trailing_step` para capturar más movimiento.")

    if not actions:
        actions.append("No se requieren cambios significativos. Mantener configuración actual.")

    return actions


def generate_report(trades, analysis, patterns):
    """Genera el archivo Markdown para Trae"""
    today = datetime.utcnow().strftime("%d %b %Y")

    total_trades = len(trades)
    total_wins = sum(1 for t in trades if t["pnl_usd"] > 0)
    total_pnl = sum(t["pnl_usd"] for t in trades)

    report = f"""# REPORTE DIARIO AURA-X - {today}

> Generado automáticamente para consumo del Agente Trae.
> Este reporte analiza las operaciones del día y sugiere ajustes a `config.json`.

## 📊 RESUMEN GENERAL
- **Total de operaciones:** {total_trades}
- **Ganadas:** {total_wins} ({total_wins/total_trades*100:.0f}% win rate) | **Perdidas:** {total_trades - total_wins}
- **P&L Neto:** ${total_pnl:+.2f} USD
- **Activos operados:** {', '.join(set(t["symbol"] for t in trades)) if trades else "Ninguno"}

"""

    # Desglose por activo
    for symbol, data in analysis.items():
        report += f"""## 📈 {symbol}
- Operaciones: {data["total"]} | Win Rate: {data["win_rate"]:.1f}%
- P&L Neto: ${data["net_pnl"]:+.2f} | Profit Factor: {data["profit_factor"]:.2f}
- Ganancia promedio: ${data["avg_win"]:+.2f} | Pérdida promedio: ${data["avg_loss"]:+.2f}

"""

    # Patrones detectados
    if patterns["winners"]:
        report += "## 🟢 PATRONES GANADORES (A APROVECHAR)\n"
        for p in patterns["winners"]:
            report += f"{p}\n"
        report += "\n"

    if patterns["losers"]:
        report += "## 🔴 PATRONES PERDEDORES (A EVITAR)\n"
        for p in patterns["losers"]:
            report += f"{p}\n"
        report += "\n"

    if patterns["management"]:
        report += "## 🟡 GESTIÓN DE SALIDA\n"
        for p in patterns["management"]:
            report += f"{p}\n"
        report += "\n"

    # Acciones para Trae
    current_config_data = {}
    try:
        with open(CONFIG_PATH, 'r') as f:
            current_config_data = json.load(f)
    except:
        pass

    actions = generate_trae_actions(patterns, current_config_data)
    report += "## 🎯 ACCIONES PARA TRAE (MODIFICAR config.json)\n"
    report += "**Regla: Solo modificar valores numéricos en config.json. No tocar código Rust ni Python.**\n\n"
    for i, action in enumerate(actions, 1):
        report += f"{i}. {action}\n"

    report += f"""
---

*Reporte generado el {datetime.utcnow().isoformat()}Z por Aura-X Intelligence Module*
"""

    return report


def main():
    print("📊 [Aura-X Intelligence] Generando reporte diario...")

    conn = init_db()
    trades = get_today_trades(conn)

    if not trades:
        print("⚠️  No hay operaciones registradas hoy. Generando reporte vacío.")
        report = f"""# REPORTE DIARIO AURA-X - {datetime.utcnow().strftime('%d %b %Y')}

## 📊 RESUMEN
- No se registraron operaciones hoy.
- El sistema puede haber estado en pausa o el mercado no presentó condiciones válidas.

## 🎯 ACCIONES PARA TRAE
1. Revisar si los filtros en `config.json` son demasiado restrictivos.
2. Verificar que la conexión al broker esté activa.
"""
    else:
        analysis = analyze_trades(trades)
        patterns = find_patterns(analysis)
        report = generate_report(trades, analysis, patterns)

    with open(OUTPUT_PATH, 'w') as f:
        f.write(report)
        
    print("✅ Reporte generado: DAILY_INTEL.md")
    print(f"📊 {len(trades)} operaciones analizadas")

    conn.close()


if __name__ == "__main__":
    main()
</parameter>
<parameter name="task_progress">
- [x] Leer y analizar archivo de chat exportado
- [x] Analizar la estructura actual del proyecto bot
- [x] Identificar funcionalidades mencionadas en el chat
- [x] Comparar con funcionalidades existentes en el bot
- [x] Generar lista de integraciones pendientes
- [ ] Fase 1: Sistema de auto-adaptación diaria
  - [x] Crear config.json base (arreglado)
  - [x] Crear generate_daily_intel.py
  - [ ] Extender signal_memory para análisis estadístico
  - [ ] Integrar hot-reload en main.py
- [ ] Fase 2: Motor ONNX para ML
- [ ] Fase 3: Motor Rust para Risk Manager
- [ ] Fase 4: Mejoras Brain Cline
- [ ] Fase 5: Mejoras Risk Manager
</parameter>
</write_to_file>