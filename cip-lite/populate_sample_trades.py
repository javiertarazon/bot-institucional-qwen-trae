#!/usr/bin/env python3
"""
Script para poblar la base de datos con trades de ejemplo
Simula un día completo de operaciones para validar el sistema
"""

import sys
import os
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

# Rutas
PROJECT_ROOT = Path(__file__).parent
DB_PATH = PROJECT_ROOT / "data" / "trades.db"

def populate_sample_data():
    """Pobla la base de datos con trades simulados del día actual"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Crear tabla
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

    # Limpiar trades previos del día
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cursor.execute("DELETE FROM trades WHERE DATE(timestamp) = ?", (today,))

    # Generar trades simulados
    today_start = datetime.utcnow().replace(hour=8, minute=0, second=0, microsecond=0)

    trades = []
    symbols_config = {
        'XAUUSD': {'price': 2350.0, 'spread': (25, 40), 'rsi': (35, 70), 'atr': (1.0, 3.0), 'body': (40, 75)},
        'EURUSD': {'price': 1.0850, 'spread': (5, 15), 'rsi': (40, 65), 'atr': (0.0008, 0.0015), 'body': (35, 70)}
    }

    random.seed(42)
    trade_id = 0

    for hour in range(8, 22):  # Sesión principal
        n_trades = random.randint(2, 6)
        for _ in range(n_trades):
            symbol = random.choice(list(symbols_config.keys()))
            cfg = symbols_config[symbol]
            direction = random.choice(['BUY', 'SELL'])

            # Generar resultado (60% ganador)
            is_winner = random.random() < 0.58

            if is_winner:
                pnl_points = random.uniform(80, 180)
                exit_reason = random.choice(['TP_HIT', 'TRAILING', 'TP_HIT'])
            else:
                pnl_points = -random.uniform(60, 120)
                exit_reason = random.choice(['SL_HIT', 'SL_HIT', 'SIGNAL'])

            lot_size = 0.01 if symbol == 'XAUUSD' else 0.05
            pnl_usd = pnl_points * 0.1 * lot_size * 10  # Aproximación

            # Condiciones de entrada
            rsi = random.uniform(*cfg['rsi'])
            atr = random.uniform(*cfg['atr'])
            spread = random.uniform(*cfg['spread'])
            body_pct = random.uniform(*cfg['body'])
            regime = random.choice(['MOMENTUM', 'LATERAL', 'TRANSITION'])

            timestamp = today_start + timedelta(hours=hour, minutes=random.randint(0, 59))
            duration = random.randint(30, 600)

            trades.append({
                'timestamp': timestamp.isoformat(),
                'symbol': symbol,
                'direction': direction,
                'entry_price': cfg['price'],
                'exit_price': cfg['price'] + (pnl_points * 0.01 if symbol == 'XAUUSD' else pnl_points * 0.0001),
                'lot_size': lot_size,
                'pnl_usd': round(pnl_usd, 2),
                'pnl_points': round(pnl_points, 1),
                'duration_seconds': duration,
                'regime': regime,
                'rsi_at_entry': round(rsi, 1),
                'atr_at_entry': round(atr, 4),
                'spread_at_entry': round(spread, 1),
                'candle_body_pct': round(body_pct, 1),
                'hour_utc': hour,
                'exit_reason': exit_reason,
                'sl_distance': 100 if symbol == 'XAUUSD' else 10,
                'tp_distance': 150 if symbol == 'XAUUSD' else 15,
            })
            trade_id += 1

    # Insertar trades
    for t in trades:
        cursor.execute('''
            INSERT INTO trades (timestamp, symbol, direction, entry_price, exit_price,
                lot_size, pnl_usd, pnl_points, duration_seconds, regime,
                rsi_at_entry, atr_at_entry, spread_at_entry, candle_body_pct,
                hour_utc, exit_reason, sl_distance, tp_distance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            t['timestamp'], t['symbol'], t['direction'], t['entry_price'], t['exit_price'],
            t['lot_size'], t['pnl_usd'], t['pnl_points'], t['duration_seconds'], t['regime'],
            t['rsi_at_entry'], t['atr_at_entry'], t['spread_at_entry'], t['candle_body_pct'],
            t['hour_utc'], t['exit_reason'], t['sl_distance'], t['tp_distance']
        ))

    conn.commit()

    # Verificar
    cursor.execute("SELECT COUNT(*) FROM trades WHERE DATE(timestamp) = ?", (today,))
    count = cursor.fetchone()[0]

    print(f"✅ {count} trades insertados para {today}")

    # Mostrar resumen
    cursor.execute("""
        SELECT symbol,
               COUNT(*) as total,
               SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END) as wins,
               ROUND(SUM(pnl_usd), 2) as pnl
        FROM trades WHERE DATE(timestamp) = ?
        GROUP BY symbol
    """, (today,))

    print("\nResumen por activo:")
    print(f"{'Symbol':<10} {'Total':<8} {'Wins':<8} {'PnL':<10}")
    print("-" * 40)
    for row in cursor.fetchall():
        print(f"{row[0]:<10} {row[1]:<8} {row[2]:<8} ${row[3]:<10}")

    conn.close()


if __name__ == "__main__":
    populate_sample_data()
