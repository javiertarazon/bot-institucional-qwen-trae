#!/usr/bin/env python3
"""
📥 Historical Data Downloader (CCXT → Parquet)
Descarga datos OHLCV históricos de Binance para las top 10 criptos
Guarda en formato Parquet para eficiencia y velocidad
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ccxt
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import argparse
import time
import json
import structlog
import warnings
warnings.filterwarnings("ignore")

logger = structlog.get_logger()

# ==================== CONFIGURACIÓN ====================
DATA_DIR = Path(__file__).parent.parent / "data" / "historical"
DATA_DIR.mkdir(parents=True, exist_ok=True)

TOP_10_CRYPTOS = [
    "BTC/USDT",
    "ETH/USDT",
    "SOL/USDT",
    "XRP/USDT",
    "ADA/USDT",
    "DOGE/USDT",
    "DOT/USDT",
    "AVAX/USDT",
    "MATIC/USDT",
    "LINK/USDT",
]

TIMEFRAME = "1h"
DEFAULT_YEARS = 2
MAX_CANDLES_PER_REQUEST = 1000  # CCXT limit
RATE_LIMIT_DELAY = 0.5  # segundos entre requests


def get_exchange():
    """Inicializa exchange Binance con rate limiting"""
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'rateLimit': 1200,
        'options': {
            'defaultType': 'spot',
        }
    })
    return exchange


def fetch_ohlcv_range(exchange, symbol: str, timeframe: str, 
                      since: int, limit: int = MAX_CANDLES_PER_REQUEST) -> list:
    """
    Fetch OHLCV con reintentos y paginación manual.
    """
    all_ohlcv = []
    current_since = since
    retries = 3
    
    while True:
        try:
            ohlcv = exchange.fetch_ohlcv(
                symbol, timeframe, 
                since=current_since, 
                limit=limit
            )
            
            if not ohlcv or len(ohlcv) == 0:
                break
            
            all_ohlcv.extend(ohlcv)
            
            # Si recibimos menos del límite, hemos llegado al final
            if len(ohlcv) < limit:
                break
            
            # Avanzar al siguiente bloque
            current_since = ohlcv[-1][0] + 1
            
            # Rate limiting
            time.sleep(RATE_LIMIT_DELAY)
            
        except ccxt.RateLimitExceeded as e:
            wait_time = 10
            logger.warning(f"Rate limit exceeded. Waiting {wait_time}s...")
            time.sleep(wait_time)
            retries -= 1
            if retries <= 0:
                raise
            
        except ccxt.NetworkError as e:
            logger.warning(f"Network error: {e}. Retrying in 5s...")
            time.sleep(5)
            retries -= 1
            if retries <= 0:
                raise
            
        except Exception as e:
            logger.error(f"Error fetching {symbol}: {e}")
            raise
    
    return all_ohlcv


def ohlcv_to_dataframe(ohlcv: list) -> pd.DataFrame:
    """Convierte lista OHLCV a DataFrame limpio"""
    if not ohlcv:
        return pd.DataFrame()
    
    df = pd.DataFrame(
        ohlcv,
        columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
    )
    
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    
    # Asegurar tipos numéricos
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Eliminar duplicados
    df = df[~df.index.duplicated(keep='last')]
    
    # Ordenar por timestamp
    df.sort_index(inplace=True)
    
    return df


def download_symbol(exchange, symbol: str, years: int = DEFAULT_YEARS,
                    force: bool = False) -> pd.DataFrame:
    """
    Descarga datos históricos para un símbolo.
    Si ya existe archivo, actualiza incrementalmente.
    """
    parquet_path = DATA_DIR / f"{symbol.replace('/', '_')}.parquet"
    
    # Cargar datos existentes si los hay
    existing_df = pd.DataFrame()
    if parquet_path.exists() and not force:
        try:
            existing_df = pd.read_parquet(parquet_path)
            logger.info(f"Datos existentes cargados: {symbol} ({len(existing_df)} velas)")
        except Exception as e:
            logger.warning(f"No se pudieron cargar datos existentes: {e}")
    
    # Determinar desde cuándo descargar
    now = datetime.now()
    
    if not existing_df.empty and not force:
        # Descargar solo datos faltantes (últimas 100 velas para asegurar solapamiento)
        last_timestamp = existing_df.index[-1]
        since = int(last_timestamp.timestamp() * 1000) - (100 * 3600 * 1000)  # 100h antes por seguridad
        logger.info(f"Actualizando {symbol} desde {last_timestamp}")
    else:
        # Descarga completa
        since_date = now - timedelta(days=years * 365)
        since = int(since_date.timestamp() * 1000)
        logger.info(f"Descarga completa {symbol} desde {since_date.date()}")
    
    # Fetch OHLCV
    logger.info(f"Descargando {symbol}...")
    ohlcv = fetch_ohlcv_range(exchange, symbol, TIMEFRAME, since)
    
    if not ohlcv:
        logger.warning(f"No se obtuvieron datos para {symbol}")
        return existing_df
    
    new_df = ohlcv_to_dataframe(ohlcv)
    
    if new_df.empty:
        return existing_df
    
    # Combinar con datos existentes
    if not existing_df.empty:
        combined = pd.concat([existing_df, new_df])
        combined = combined[~combined.index.duplicated(keep='last')]
        combined.sort_index(inplace=True)
    else:
        combined = new_df
    
    # Guardar
    combined.to_parquet(parquet_path, compression='snappy')
    
    logger.info(f"✅ {symbol}: {len(combined)} velas guardadas "
                f"({combined.index[0].date()} → {combined.index[-1].date()})")
    
    return combined


def get_exchange_info(exchange) -> dict:
    """Obtiene información del exchange para validación"""
    try:
        markets = exchange.load_markets()
        info = {}
        for symbol in TOP_10_CRYPTOS:
            if symbol in markets:
                m = markets[symbol]
                info[symbol] = {
                    'active': m['active'],
                    'precision': m['precision'],
                    'limits': m['limits'],
                }
        return info
    except Exception as e:
        logger.error(f"Error obteniendo info del exchange: {e}")
        return {}


def download_all(years: int = DEFAULT_YEARS, symbols: list = None,
                 force: bool = False) -> dict:
    """Descarga datos para todos los símbolos"""
    if symbols is None:
        symbols = TOP_10_CRYPTOS
    
    exchange = get_exchange()
    
    # Validar símbolos disponibles
    exchange.load_markets()
    valid_symbols = [s for s in symbols if s in exchange.markets]
    invalid_symbols = [s for s in symbols if s not in exchange.markets]
    
    if invalid_symbols:
        logger.warning(f"Símbolos no encontrados: {invalid_symbols}")
    
    if not valid_symbols:
        logger.error("No hay símbolos válidos para descargar")
        return {}
    
    logger.info(f"Iniciando descarga de {len(valid_symbols)} símbolos...")
    logger.info(f"Símbolos: {valid_symbols}")
    
    results = {}
    for symbol in valid_symbols:
        try:
            df = download_symbol(exchange, symbol, years, force)
            results[symbol] = {
                'status': 'success',
                'rows': len(df),
                'start': str(df.index[0].date()) if len(df) > 0 else 'N/A',
                'end': str(df.index[-1].date()) if len(df) > 0 else 'N/A',
            }
        except Exception as e:
            logger.error(f"Error descargando {symbol}: {e}")
            results[symbol] = {'status': 'error', 'error': str(e)}
    
    # Generar reporte resumen
    report_path = DATA_DIR / "download_report.json"
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'timeframe': TIMEFRAME,
            'years': years,
            'results': results
        }, f, indent=2, default=str)
    
    return results


def get_combined_dataset(symbols: list = None, 
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
    """
    Carga y combina datos de múltiples símbolos en un solo dataset.
    Útil para entrenamiento del modelo ONNX.
    """
    if symbols is None:
        symbols = TOP_10_CRYPTOS
    
    all_dfs = []
    
    for symbol in symbols:
        parquet_path = DATA_DIR / f"{symbol.replace('/', '_')}.parquet"
        if not parquet_path.exists():
            logger.warning(f"Archivo no encontrado: {parquet_path}")
            continue
        
        df = pd.read_parquet(parquet_path)
        
        if df.empty:
            continue
        
        # Filtro por fecha
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        if df.empty:
            continue
        
        # Añadir columna de símbolo
        df['symbol'] = symbol
        
        all_dfs.append(df)
    
    if not all_dfs:
        return pd.DataFrame()
    
    combined = pd.concat(all_dfs, axis=0)
    combined.sort_index(inplace=True)
    
    logger.info(f"Dataset combinado: {len(combined)} filas, "
                f"{combined['symbol'].nunique()} símbolos")
    
    return combined


def print_summary(results: dict):
    """Imprime resumen de la descarga"""
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE DESCARGA DE DATOS HISTÓRICOS")
    print("=" * 70)
    
    success = [s for s, r in results.items() if r['status'] == 'success']
    errors = [s for s, r in results.items() if r['status'] == 'error']
    
    print(f"\n✅ Exitosos: {len(success)}/{len(results)}")
    print(f"❌ Errores: {len(errors)}")
    
    if success:
        print(f"\n📈 Símbolos descargados:")
        for symbol in success:
            r = results[symbol]
            print(f"   {symbol:15s} → {r['rows']:6d} velas  ({r['start']} → {r['end']})")
    
    if errors:
        print(f"\n⚠️  Errores:")
        for symbol in errors:
            r = results[symbol]
            print(f"   {symbol}: {r.get('error', 'unknown')}")
    
    print(f"\n💾 Datos guardados en: {DATA_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descargar datos históricos de criptos vía CCXT")
    parser.add_argument('--symbols', nargs='+', 
                        help='Símbolos a descargar (default: top 10)')
    parser.add_argument('--years', type=int, default=DEFAULT_YEARS,
                        help=f'Años de historia (default: {DEFAULT_YEARS})')
    parser.add_argument('--force', action='store_true',
                        help='Forzar descarga completa (ignorar caché)')
    parser.add_argument('--list', action='store_true',
                        help='Listar símbolos disponibles')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("📥 CIP - Historical Data Downloader v1.0")
    print("   Fuente: Binance (CCXT) | Timeframe: 1h")
    print("=" * 70)
    
    if args.list:
        print("\n🔍 Símbolos disponibles por defecto:")
        for s in TOP_10_CRYPTOS:
            print(f"   • {s}")
        print("\nUsa --symbols SYM1 SYM2 ... para personalizar")
        sys.exit(0)
    
    symbols = args.symbols or TOP_10_CRYPTOS
    
    print(f"\n⏳ Descargando {len(symbols)} símbolos...")
    print(f"   Período: últimos {args.years} años")
    print(f"   Fuerza: {'SÍ' if args.force else 'NO (incremental)'}")
    
    results = download_all(years=args.years, symbols=symbols, force=args.force)
    
    print_summary(results)
    
    # Mostrar ejemplo de uso del dataset combinado
    print("\n💡 Para entrenar el modelo ONNX con estos datos:")
    print("   python 01_data_ingestion/historical_downloader.py --list")
    print("   python python_brain/train_and_export_onnx.py")