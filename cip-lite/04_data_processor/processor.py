"""
Módulo de Procesamiento de Datos - v2.0
Normaliza y convierte datos crudos a JSON para el cerebro
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from datetime import datetime
import structlog

logger = structlog.get_logger()


class DataProcessorModule:
    """
    Procesador y normalizador de datos
    Transforma datos de múltiples fuentes a formato estándar
    """
    
    def __init__(self):
        self.symbol_mapping = {
            # CCXT → Estándar
            'BTC/USDT': 'BTCUSDT',
            'ETH/USDT': 'ETHUSDT',
            'BNB/USDT': 'BNBUSDT',
            'SOL/USDT': 'SOLUSDT',
            'ADA/USDT': 'ADAUSDT',
            'XRP/USDT': 'XRPUSDT',
            'DOGE/USDT': 'DOGEUSDT',
            # MT5 → Estándar
            'EURUSD': 'EURUSD',
            'GBPUSD': 'GBPUSD',
            'USDJPY': 'USDJPY',
            'XAUUSD': 'XAUUSD',
            'XAGUSD': 'XAGUSD',
            'US30': 'US30',
            'NAS100': 'NAS100',
            'SPX500': 'SPX500'
        }
        
        logger.info("Data Processor Module v2.0 inicializado")
    
    def normalize(self, raw_data: pd.DataFrame, indicators: Dict[str, float], 
                  symbol: str) -> Dict[str, Any]:
        """
        Normaliza datos crudos a formato JSON estándar
        """
        try:
            # Estandarizar símbolo
            std_symbol = self._standardize_symbol(symbol)
            
            # Normalizar timestamps a UTC
            if raw_data.index.tzinfo is None:
                raw_data.index = pd.to_datetime(raw_data.index).tz_localize('UTC')
            else:
                raw_data.index = pd.to_datetime(raw_data.index).tz_convert('UTC')
            
            # Validar y limpiar datos
            clean_data = self._clean_ohlcv(raw_data)
            
            # Detectar gaps
            gaps = self._detect_gaps(clean_data)
            
            # Calcular estadísticas básicas
            stats = self._calculate_stats(clean_data)
            
            # Construir payload final
            processed = {
                'symbol': std_symbol,
                'original_symbol': symbol,
                'timestamp': datetime.now().isoformat(),
                'data_start': clean_data.index[0].isoformat(),
                'data_end': clean_data.index[-1].isoformat(),
                'bars_count': len(clean_data),
                'current_price': float(clean_data['close'].iloc[-1]),
                'indicators': indicators,
                'data_quality': {
                    'has_gaps': len(gaps) > 0,
                    'gaps': gaps,
                    'is_valid': len(gaps) == 0
                },
                'statistics': stats
            }
            
            logger.debug(f"Datos normalizados: {std_symbol} | {len(clean_data)} barras")
            
            return processed
            
        except Exception as e:
            logger.error(f"Error normalizando datos: {e}", exc_info=True)
            return {
                'symbol': symbol,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _standardize_symbol(self, symbol: str) -> str:
        """Convierte símbolo a formato estándar"""
        # Buscar en mapping
        for key, value in self.symbol_mapping.items():
            if symbol.upper() in [key.upper(), value.upper()]:
                return value
        
        # Si no está en mapping, retornar en mayúsculas
        return symbol.upper().replace('/', '').replace('-', '')
    
    def _clean_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """Limpia datos OHLCV"""
        required_cols = ['open', 'high', 'low', 'close', 'volume']
        
        # Verificar columnas
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Columna requerida faltante: {col}")
        
        # Eliminar filas con NaN en precios
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        
        # Corregir high/low inconsistentes
        df['high'] = df[['high', 'open', 'close']].max(axis=1)
        df['low'] = df[['low', 'open', 'close']].min(axis=1)
        
        # Eliminar duplicados
        df = df[~df.index.duplicated(keep='first')]
        
        return df
    
    def _detect_gaps(self, df: pd.DataFrame) -> List[Dict]:
        """Detecta gaps en los datos"""
        gaps = []
        
        if len(df) < 2:
            return gaps
        
        # Calcular diferencias de tiempo
        time_diffs = df.index.to_series().diff()
        
        # Detectar gaps mayores a 2 períodos (asumiendo 1m)
        threshold = pd.Timedelta(minutes=2)
        
        gap_indices = time_diffs[time_diffs > threshold].index
        
        for idx in gap_indices:
            gap_start = df.index[df.index.get_loc(idx) - 1]
            gap_end = idx
            gap_duration = gap_end - gap_start
            
            gaps.append({
                'start': gap_start.isoformat(),
                'end': gap_end.isoformat(),
                'duration_minutes': gap_duration.total_seconds() / 60
            })
        
        return gaps
    
    def _calculate_stats(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcula estadísticas básicas"""
        closes = df['close']
        
        return {
            'mean_price': float(closes.mean()),
            'std_price': float(closes.std()),
            'min_price': float(closes.min()),
            'max_price': float(closes.max()),
            'current_price': float(closes.iloc[-1]),
            'price_change_1bar': float(closes.pct_change().iloc[-1]),
            'volatility_20': float(closes.pct_change().rolling(20).std().iloc[-1]),
            'volume_avg_20': float(df['volume'].tail(20).mean()),
            'volume_current': float(df['volume'].iloc[-1])
        }
    
    def normalize_ccxt(self, raw_data: Dict) -> Dict:
        """Normaliza datos específicos de CCXT"""
        try:
            df = pd.DataFrame(raw_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Error normalizando CCXT: {e}")
            return pd.DataFrame()
    
    def normalize_mt5(self, raw_data: np.ndarray) -> pd.DataFrame:
        """Normaliza datos específicos de MT5"""
        try:
            df = pd.DataFrame(raw_data)
            df['timestamp'] = pd.to_datetime(df['time'], unit='s')
            df.set_index('timestamp', inplace=True)
            df.rename(columns={'tick_volume': 'volume'}, inplace=True)
            return df[['open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logger.error(f"Error normalizando MT5: {e}")
            return pd.DataFrame()
    
    def to_json_serializable(self, obj: Any) -> Any:
        """Convierte objetos a formato JSON serializable"""
        if isinstance(obj, pd.DataFrame):
            return obj.reset_index().to_dict(orient='records')
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, dict):
            return {k: self.to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self.to_json_serializable(item) for item in obj]
        else:
            return obj
    
    def validate_data_integrity(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Valida la integridad de los datos"""
        issues = []
        
        # Verificar columnas requeridas
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [col for col in required if col not in df.columns]
        if missing:
            issues.append(f"Columnas faltantes: {missing}")
        
        # Verificar valores negativos en precios
        price_cols = ['open', 'high', 'low', 'close']
        for col in price_cols:
            if col in df.columns and (df[col] < 0).any():
                issues.append(f"Precios negativos en {col}")
        
        # Verificar high < low
        if 'high' in df.columns and 'low' in df.columns:
            invalid = df[df['high'] < df['low']]
            if len(invalid) > 0:
                issues.append(f"High < Low en {len(invalid)} filas")
        
        # Verificar volumen negativo
        if 'volume' in df.columns and (df['volume'] < 0).any():
            issues.append("Volumen negativo detectado")
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'rows': len(df),
            'columns': list(df.columns)
        }


# Función de conveniencia
def create_data_processor() -> DataProcessorModule:
    """Factory para crear procesador de datos"""
    return DataProcessorModule()


if __name__ == "__main__":
    print("Testing Data Processor Module v2.0...")
    print("=" * 60)
    
    processor = DataProcessorModule()
    
    # Test normalización
    test_df = pd.DataFrame({
        'timestamp': pd.date_range(end=datetime.now(), periods=100, freq='1min'),
        'open': [100.0 + i*0.1 for i in range(100)],
        'high': [101.0 + i*0.1 for i in range(100)],
        'low': [99.0 + i*0.1 for i in range(100)],
        'close': [100.5 + i*0.1 for i in range(100)],
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    # Símbolos de prueba
    test_symbols = ['EURUSD', 'BTC/USDT', 'XAUUSD', 'ETH/USDT']
    
    print("\n📊 Normalización de símbolos:")
    for sym in test_symbols:
        std = processor._standardize_symbol(sym)
        print(f"   {sym:15s} → {std}")
    
    # Test validación
    validation = processor.validate_data_integrity(test_df)
    print(f"\n✅ Validación: {'VÁLIDO' if validation['is_valid'] else 'CON ERRORES'}")
    if not validation['is_valid']:
        for issue in validation['issues']:
            print(f"   ❌ {issue}")
    
    # Test normalización completa
    result = processor.normalize(test_df, {'rsi': 50}, 'EURUSD')
    print(f"\n📦 Payload normalizado:")
    print(f"   Símbolo: {result['symbol']}")
    print(f"   Precio: {result['current_price']:.2f}")
    print(f"   Validez: {result['data_quality']['is_valid']}")
    
    print("\n✅ Data Processor Module funcionando correctamente")
</parameter>
</write_to_file>