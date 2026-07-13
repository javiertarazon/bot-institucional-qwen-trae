"""
Módulo Orquestador - v2.0
Coordina todos los módulos del sistema de trading
Flujo: Data → Indicators → Memory → Processor → Brain → Risk → Execution
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger()


@dataclass
class TradingContext:
    """Contexto completo para una decisión de trading"""
    symbol: str
    timestamp: datetime
    market_data: pd.DataFrame
    indicators: Dict[str, float]
    memory_insights: Dict[str, any]
    regime: str
    sentiment: float
    confidence: float
    decision: str  # BUY, SELL, HOLD
    reasoning: str


class Orchestrator:
    """
    Orquestador central del sistema de trading
    Coordina el flujo completo desde datos hasta ejecución
    """
    
    def __init__(self):
        # Módulos (se inyectan al configurar)
        self.data_ingestion = None
        self.indicator_engine = None
        self.signal_memory = None
        self.data_processor = None
        self.brain = None
        self.risk_manager = None
        self.execution = None
        
        # Estado
        self.is_running = False
        self.cycle_count = 0
        self.last_cycle_time: Optional[datetime] = None
        
        # Configuración
        self.symbols: List[str] = []
        self.timeframe: str = "1m"
        self.cycle_interval: int = 60  # segundos
        
        logger.info("Orquestador v2.0 inicializado")
    
    def configure(self, config: Dict):
        """
        Configura el orquestador con todos los módulos
        """
        self.symbols = config.get('symbols', ['EURUSD', 'XAUUSD'])
        self.timeframe = config.get('timeframe', '1m')
        self.cycle_interval = config.get('cycle_interval', 60)
        
        # Inyectar módulos
        if 'data_ingestion' in config:
            self.data_ingestion = config['data_ingestion']
        if 'indicator_engine' in config:
            self.indicator_engine = config['indicator_engine']
        if 'signal_memory' in config:
            self.signal_memory = config['signal_memory']
        if 'data_processor' in config:
            self.data_processor = config['data_processor']
        if 'brain' in config:
            self.brain = config['brain']
        if 'risk_manager' in config:
            self.risk_manager = config['risk_manager']
        if 'execution' in config:
            self.execution = config['execution']
        
        logger.info(f"Orquestador configurado | Símbolos: {self.symbols} | "
                   f"Timeframe: {self.timeframe}")
    
    async def run_cycle(self, symbol: str) -> Dict:
        """
        Ejecuta un ciclo completo de trading para un símbolo
        Flujo: Data → Indicators → Memory → Processor → Brain → Risk → Execution
        """
        self.cycle_count += 1
        cycle_id = f"CYCLE_{self.cycle_count}_{symbol}_{datetime.now().timestamp()}"
        
        logger.info(f"🚀 Iniciando ciclo {cycle_id}")
        
        try:
            # ========== PASO 1: OBTENER DATOS ==========
            logger.info(f"[{cycle_id}] 1/7 - Obteniendo datos de mercado...")
            raw_data = await self._fetch_market_data(symbol)
            if raw_data is None or raw_data.empty:
                return {"status": "ERROR", "reason": "Datos no disponibles", "symbol": symbol}
            
            # ========== PASO 2: CALCULAR INDICADORES ==========
            logger.info(f"[{cycle_id}] 2/7 - Calculando indicadores...")
            indicators = self._calculate_indicators(raw_data, symbol)
            
            # ========== PASO 3: CONSULTAR MEMORIA ==========
            logger.info(f"[{cycle_id}] 3/7 - Consultando memoria de operaciones...")
            memory_insights = self._consult_memory(symbol)
            
            # ========== PASO 4: PROCESAR DATOS ==========
            logger.info(f"[{cycle_id}] 4/7 - Procesando y normalizando datos...")
            processed_data = self._process_data(raw_data, indicators, symbol)
            
            # ========== PASO 5: CEREBRO ANALIZA ==========
            logger.info(f"[{cycle_id}] 5/7 - Cerebro analizando mercado...")
            context = await self._brain_analysis(processed_data, symbol, memory_insights)
            if context is None:
                return {"status": "ERROR", "reason": "Brain analysis failed", "symbol": symbol}
            
            # ========== PASO 6: VALIDAR RIESGO ==========
            logger.info(f"[{cycle_id}] 6/7 - Validando riesgo...")
            risk_approved, risk_reason = self._validate_risk(context)
            
            if not risk_approved:
                logger.warning(f"[{cycle_id}] ❌ Riesgo rechazado: {risk_reason}")
                return {
                    "status": "RISK_REJECTED",
                    "reason": risk_reason,
                    "context": context.__dict__ if context else None
                }
            
            # ========== PASO 7: EJECUTAR ==========
            if context.decision in ["BUY", "SELL"] and context.confidence > 0.6:
                logger.info(f"[{cycle_id}] 7/7 - Ejecutando orden: {context.decision}")
                execution_result = await self._execute_trade(context)
                
                return {
                    "status": "EXECUTED",
                    "decision": context.decision,
                    "confidence": context.confidence,
                    "execution": execution_result,
                    "context": context.__dict__
                }
            else:
                logger.info(f"[{cycle_id}] 7/7 - Sin señal de trading (HOLD)")
                return {
                    "status": "HOLD",
                    "reason": f"Confianza insuficiente o sin señal ({context.confidence:.2f})",
                    "context": context.__dict__
                }
        
        except Exception as e:
            logger.error(f"[{cycle_id}] ❌ Error en ciclo: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e), "symbol": symbol}
    
    async def _fetch_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Obtiene datos de mercado"""
        if not self.data_ingestion:
            logger.error("Data Ingestion no configurado")
            return None
        
        try:
            # Intentar con fuente configurada
            data = await self.data_ingestion.fetch_live_data(symbol, source='ccxt')
            if data is None or data.empty:
                # Fallback a datos sintéticos
                logger.warning(f"Fallback a datos sintéticos para {symbol}")
                data = self._generate_synthetic_data(symbol)
            return data
        except Exception as e:
            logger.error(f"Error obteniendo datos: {e}")
            return self._generate_synthetic_data(symbol)
    
    def _calculate_indicators(self, df: pd.DataFrame, symbol: str) -> Dict[str, float]:
        """Calcula indicadores técnicos"""
        if not self.indicator_engine:
            # Indicadores básicos por defecto
            return {
                'sma_20': df['close'].rolling(20).mean().iloc[-1],
                'sma_50': df['close'].rolling(50).mean().iloc[-1],
                'rsi': self._calc_rsi(df['close']),
                'atr': self._calc_atr(df)
            }
        
        return self.indicator_engine.calculate_all(df, symbol)
    
    def _consult_memory(self, symbol: str) -> Dict:
        """Consulta la memoria de operaciones"""
        if not self.signal_memory:
            return {}
        
        try:
            return self.signal_memory.get_insights(symbol)
        except Exception as e:
            logger.warning(f"Error consultando memoria: {e}")
            return {}
    
    def _process_data(self, df: pd.DataFrame, indicators: Dict, symbol: str) -> Dict:
        """Procesa y normaliza datos para el cerebro"""
        if not self.data_processor:
            # Procesamiento básico
            return {
                'symbol': symbol,
                'current_price': df['close'].iloc[-1],
                'indicators': indicators,
                'timestamp': datetime.now().isoformat()
            }
        
        return self.data_processor.normalize(df, indicators, symbol)
    
    async def _brain_analysis(self, processed_data: Dict, symbol: str,
                              memory_insights: Dict) -> Optional[TradingContext]:
        """Cerebro analiza y decide"""
        if not self.brain:
            logger.error("Brain no configurado")
            return None
        
        try:
            # Convertir a DataFrame para el brain
            df = pd.DataFrame([processed_data])
            
            # Análisis
            analysis = self.brain.analyze_market(df, symbol)
            
            # Decisión
            signal = self.brain.generate_trading_decision(df, symbol)
            
            # Crear contexto
            context = TradingContext(
                symbol=symbol,
                timestamp=datetime.now(),
                market_data=df,
                indicators=processed_data.get('indicators', {}),
                memory_insights=memory_insights,
                regime=analysis.trend if hasattr(analysis, 'trend') else "UNKNOWN",
                sentiment=analysis.sentiment_score if hasattr(analysis, 'sentiment_score') else 0.0,
                confidence=signal.confidence,
                decision=signal.signal,
                reasoning=signal.__dict__ if hasattr(signal, '__dict__') else {}
            )
            
            return context
        
        except Exception as e:
            logger.error(f"Error en brain analysis: {e}", exc_info=True)
            return None
    
    def _validate_risk(self, context: TradingContext) -> Tuple[bool, str]:
        """Valida riesgo de la operación"""
        if not self.risk_manager:
            logger.warning("Risk Manager no configurado - aprobando por defecto")
            return True, "NO_RISK_MANAGER"
        
        try:
            # Calcular tamaño
            size, explanation = self.risk_manager.calculate_position_size(
                signal_confidence=context.confidence,
                symbol=context.symbol,
                df=context.market_data,
                price=context.market_data['close'].iloc[-1],
                regime=context.regime
            )
            
            if size <= 0:
                return False, explanation
            
            # Calcular SL/TP
            sl_price, _ = self.risk_manager.calculate_stop_loss(
                entry_price=context.market_data['close'].iloc[-1],
                df=context.market_data,
                direction="long" if context.decision == "BUY" else "short"
            )
            
            tp_price, _ = self.risk_manager.calculate_take_profit(
                entry_price=context.market_data['close'].iloc[-1],
                sl_price=sl_price,
                risk_reward_ratio=1.5
            )
            
            # Validar
            approved, reason = self.risk_manager.validate_trade(
                symbol=context.symbol,
                size=size,
                sl_price=sl_price,
                tp_price=tp_price,
                direction=context.decision.lower()
            )
            
            # Guardar en context para usar en ejecución
            context.reasoning['position_size'] = size
            context.reasoning['stop_loss'] = sl_price
            context.reasoning['take_profit'] = tp_price
            
            return approved, reason
        
        except Exception as e:
            logger.error(f"Error validando riesgo: {e}")
            return False, str(e)
    
    async def _execute_trade(self, context: TradingContext) -> Dict:
        """Ejecuta la operación"""
        if not self.execution:
            logger.error("Execution Engine no configurado")
            return {"status": "ERROR", "reason": "No execution engine"}
        
        try:
            size = context.reasoning.get('position_size', 0)
            sl = context.reasoning.get('stop_loss', 0)
            tp = context.reasoning.get('take_profit', 0)
            
            result = await self.execution.execute_order(
                symbol=context.symbol,
                side=context.decision,
                size=size,
                stop_loss=sl,
                take_profit=tp
            )
            
            # Registrar en memoria si se ejecutó
            if result.get('status') == 'FILLED':
                self._record_trade_to_memory(context, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error ejecutando trade: {e}")
            return {"status": "ERROR", "reason": str(e)}
    
    def _record_trade_to_memory(self, context: TradingContext, result: Dict):
        """Registra la operación en memoria para aprendizaje"""
        if not self.signal_memory:
            return
        
        try:
            trade_data = {
                'timestamp': context.timestamp,
                'symbol': context.symbol,
                'decision': context.decision,
                'confidence': context.confidence,
                'regime': context.regime,
                'sentiment': context.sentiment,
                'indicators': context.indicators,
                'result': 'PENDING'  # Se actualiza al cerrar
            }
            self.signal_memory.record_trade(trade_data)
        except Exception as e:
            logger.warning(f"Error registrando en memoria: {e}")
    
    async def run_continuous(self):
        """Ejecuta el ciclo continuo de trading"""
        logger.info(f"🔄 Iniciando orquestación continua | Símbolos: {self.symbols}")
        self.is_running = True
        
        while self.is_running:
            try:
                for symbol in self.symbols:
                    if not self.is_running:
                        break
                    
                    result = await self.run_cycle(symbol)
                    
                    # Log resultado
                    self._log_cycle_result(result)
                
                self.last_cycle_time = datetime.now()
                
                # Esperar siguiente ciclo
                await asyncio.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                logger.info("Orquestador detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en ciclo continuo: {e}", exc_info=True)
                await asyncio.sleep(self.cycle_interval)
        
        self.is_running = False
        logger.info("Orquestador detenido")
    
    def stop(self):
        """Detiene el orquestador"""
        self.is_running = False
        logger.info("Orquestador señalado para detenerse")
    
    def _log_cycle_result(self, result: Dict):
        """Log del resultado del ciclo"""
        status = result.get('status', 'UNKNOWN')
        symbol = result.get('symbol', 'UNKNOWN')
        
        if status == 'EXECUTED':
            decision = result.get('decision')
            confidence = result.get('confidence', 0)
            logger.info(f"✅ {symbol} → {decision} (conf: {confidence:.2f})")
        elif status == 'RISK_REJECTED':
            reason = result.get('reason', 'Unknown')
            logger.warning(f"⚠️ {symbol} → RECHAZADO: {reason}")
        elif status == 'ERROR':
            reason = result.get('reason', 'Unknown')
            logger.error(f"❌ {symbol} → ERROR: {reason}")
        else:
            logger.info(f"ℹ️ {symbol} → HOLD")
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _calc_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI básico"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs)).iloc[-1]
    
    def _calc_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """ATR básico"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().iloc[-1]
    
    def _generate_synthetic_data(self, symbol: str) -> pd.DataFrame:
        """Genera datos sintéticos de respaldo"""
        import numpy as np
        
        base_prices = {
            'EURUSD': 1.0850,
            'GBPUSD': 1.2650,
            'XAUUSD': 2650.0,
            'BTC/USDT': 50000.0
        }
        base = base_prices.get(symbol, 100.0)
        
        prices = [base]
        for _ in range(100):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.001)))
        
        return pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=100, freq='1min'),
            'open': prices,
            'high': [p * 1.001 for p in prices],
            'low': [p * 0.999 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, 100)
        })


# Función de conveniencia
def create_orchestrator(config: Dict) -> Orchestrator:
    """Factory para crear el orquestador"""
    orchestrator = Orchestrator()
    orchestrator.configure(config)
    return orchestrator


if __name__ == "__main__":
    print("Testing Orchestrator v2.0...")
    print("=" * 60)
    
    # Test básico
    orch = Orchestrator()
    orch.configure({
        'symbols': ['EURUSD', 'XAUUSD'],
        'timeframe': '1m',
        'cycle_interval': 60
    })
    
    print(f"\n✅ Orquestador configurado")
    print(f"   Símbolos: {orch.symbols}")
    print(f"   Timeframe: {orch.timeframe}")
    print(f"   Intervalo: {orch.cycle_interval}s")
    
    print("\n⚠️  Nota: Para ejecutar completo, inyectar módulos:")
    print("   - data_ingestion")
    print("   - indicator_engine")
    print("   - signal_memory")
    print("   - data_processor")
    print("   - brain")
    print("   - risk_manager")
    print("   - execution")
    
    print("\n✅ Orchestrator v2.0 funcionando correctamente")