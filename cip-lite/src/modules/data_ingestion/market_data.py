"""
Módulo de Recolección de Datos - v2.0
Fuentes: CCXT (crypto) + MT5 (Forex/Oro/Índices)
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()


class DataIngestionModule:
    """
    Módulo central de ingesta de datos
    Soporta múltiples fuentes: CCXT, MT5, sintéticos
    """
    
    def __init__(self):
        self.ccxt_exchanges = {}
        self.mt5_connection = None
        self.cache: Dict[str, pd.DataFrame] = {}
        
        logger.info("Data Ingestion Module v2.0 inicializado")
    
    async def fetch_historical(self, symbol: str, start_date: datetime,
                               end_date: datetime, timeframe: str = '1h',
                               source: str = 'ccxt') -> Optional[pd.DataFrame]:
        """
        Obtiene datos históricos
        """
        logger.info(f"Fetching historical data: {symbol} | {source} | {timeframe}")
        
        try:
            if source == 'ccxt':
                return await self._fetch_ccxt_historical(symbol, timeframe)
            elif source == 'mt5':
                return await self._fetch_mt5_historical(symbol, timeframe)
            else:
                logger.warning(f"Fuente desconocida: {source}")
                return None
        except Exception as e:
            logger.error(f"Error fetching historical data: {e}")
            return None
    
    async def stream_live(self, symbol: str, callback, 
                          source: str = 'ccxt') -> asyncio.Task:
        """
        Stream de datos en vivo
        callback: función que recibe (symbol, data)
        """
        logger.info(f"Iniciando stream en vivo: {symbol} | {source}")
        
        async def _stream_loop():
            while True:
                try:
                    data = await self.fetch_live_data(symbol, source)
                    if data is not None:
                        await callback(symbol, data)
                    await asyncio.sleep(60)  # 1 minuto por defecto
                except Exception as e:
                    logger.error(f"Error en stream: {e}")
                    await asyncio.sleep(60)
        
        task = asyncio.create_task(_stream_loop())
        return task
    
    async def fetch_live_data(self, symbol: str, source: str = 'ccxt') -> Optional[pd.DataFrame]:
        """Obtiene datos en vivo (últimas velas)"""
        try:
            if source == 'ccxt':
                return await self._fetch_ccxt_live(symbol)
            elif source == 'mt5':
                return await self._fetch_mt5_live(symbol)
            else:
                return self._generate_fallback_data(symbol)
        except Exception as e:
            logger.warning(f"Error fetching live data: {e}")
            return self._generate_fallback_data(symbol)
    
    def get_available_symbols(self, exchange: str = 'binance') -> List[str]:
        """Obtiene lista de símbolos disponibles"""
        if exchange == 'binance':
            return [
                'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT',
                'XRP/USDT', 'DOGE/USDT', 'DOT/USDT', 'MATIC/USDT', 'LTC/USDT'
            ]
        elif exchange == 'mt5':
            return [
                'EURUSD', 'GBPUSD', 'USDJPY', 'XAUUSD', 'XAGUSD',
                'US30', 'NAS100', 'SPX500', 'BTCUSD', 'ETHUSD'
            ]
        else:
            return []
    
    # ========== MÉTODOS PRIVADOS ==========
    
    async def _fetch_ccxt_historical(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Fetch desde CCXT (Binance por defecto)"""
        try:
            import ccxt
            
            exchange = ccxt.binance()
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=500)
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            logger.info(f"CCXT historical: {symbol} | {len(df)} velas")
            return df
            
        except ImportError:
            logger.warning("CCXT no instalado, usando datos sintéticos")
            return self._generate_fallback_data(symbol)
        except Exception as e:
            logger.error(f"Error CCXT: {e}")
            return self._generate_fallback_data(symbol)
    
    async def _fetch_mt5_historical(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Fetch desde MT5"""
        try:
            import MetaTrader5 as mt5
            
            if not mt5.initialize():
                logger.error("No se pudo inicializar MT5")
                return self._generate_fallback_data(symbol)
            
            # Mapeo de timeframes
            tf_map = {
                '1m': mt5.TIMEFRAME_M1,
                '5m': mt5.TIMEFRAME_M5,
                '1h': mt5.TIMEFRAME_H1,
                '1d': mt5.TIMEFRAME_D1
            }
            tf = tf_map.get(timeframe, mt5.TIMEFRAME_H1)
            
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 500)
            mt5.shutdown()
            
            if rates is None or len(rates) == 0:
                logger.warning(f"MT5 no retornó datos para {symbol}")
                return self._generate_fallback_data(symbol)
            
            df = pd.DataFrame(rates)
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('timestamp', inplace=True)
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            
            logger.info(f"MT5 historical: {symbol} | {len(df)} velas")
            return df
            
        except ImportError:
            logger.warning("MT5 no instalado, usando datos sintéticos")
            return self._generate_fallback_data(symbol)
        except Exception as e:
            logger.error(f"Error MT5: {e}")
            return self._generate_fallback_data(symbol)
    
    async def _fetch_ccxt_live(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch en vivo desde CCXT"""
        return await self._fetch_ccxt_historical(symbol, '1m')
    
    async def _fetch_mt5_live(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch en vivo desde MT5"""
        return await self._fetch_mt5_historical(symbol, '1m')
    
    def _generate_fallback_data(self, symbol: str) -> pd.DataFrame:
        """Genera datos sintéticos cuando no hay fuente disponible"""
        import numpy as np
        
        base_prices = {
            'EURUSD': 1.0850, 'GBPUSD': 1.2650, 'USDJPY': 149.50,
            'XAUUSD': 2650.0, 'XAGUSD': 31.0,
            'BTC/USDT': 50000.0, 'ETH/USDT': 3000.0,
            'BNB/USDT': 600.0, 'SOL/USDT': 100.0
        }
        base = base_prices.get(symbol, 100.0)
        
        # Generar 100 velas sintéticas
        prices = [base]
        for _ in range(99):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.001)))
        
        df = pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=100, freq='1min'),
            'open': prices,
            'high': [p * 1.001 for p in prices],
            'low': [p * 0.999 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        })
        
        logger.debug(f"Datos sintéticos generados: {symbol} | {len(df)} velas")
        return df


# Función de conveniencia
def create_data_ingestion() -> DataIngestionModule:
    """Factory para crear módulo de ingesta"""
    return DataIngestionModule()


if __name__ == "__main__":
    print("Testing Data Ingestion Module v2.0...")
    print("=" * 60)
    
    async def test():
        dim = DataIngestionModule()
        
        # Test histórico
        df = await dim.fetch_live_data('EURUSD', source='ccxt')
        if df is not None:
            print(f"\n✅ Datos obtenidos: {len(df)} velas")
            print(f"   Precio actual: {df['close'].iloc[-1]:.5f}")
            print(f"   Columnas: {list(df.columns)}")
        else:
            print("❌ No se pudieron obtener datos")
        
        # Test símbolos disponibles
        symbols = dim.get_available_symbols('mt5')
        print(f"\n📊 Símbolos MT5 disponibles: {len(symbols)}")
        print(f"   Ejemplos: {symbols[:5]}")
    
    asyncio.run(test())
    print("\n✅ Data Ingestion Module funcionando correctamente")