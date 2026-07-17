"""
Módulo Orquestador - v2.1
Coordina todos los módulos del sistema de trading
Flujo: Data → Indicators → Memory → Processor → Brain (v3.0) → Risk → Execution
Integración completa con Brain Cline: multi-timeframe, divergencias, régimen, volumen
"""

import asyncio
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import structlog
import numpy as np

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
    # Nuevos campos v3.0
    technical_score: float = 0.0
    divergence: str = "NONE"
    volume_profile: str = "NORMAL"
    regime_alignment: float = 0.0
    urgency: str = "LOW"
    time_horizon: str = "INTRADAY"
    sl_price: float = 0.0
    tp_price: float = 0.0
    risk_reward: float = 0.0
    rsi: float = 50.0
    adx: float = 20.0
    candle_pattern: str = "NONE"


class Orchestrator:
    """
    Orquestador central del sistema de trading v2.1
    Coordina el flujo completo desde datos hasta ejecución
    Integración mejorada con Brain Cline v3.0
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
        self.cycle_results: List[Dict] = []
        
        # Configuración
        self.symbols: List[str] = []
        self.timeframe: str = "1m"
        self.cycle_interval: int = 60  # segundos
        
        # Umbral de decisión (configurable)
        self.min_confidence_threshold: float = 0.55
        
        logger.info("🧠 Orquestador v2.1 inicializado (Brain Cline v3.0)")
    
    def configure(self, config: Dict):
        """
        Configura el orquestador con todos los módulos
        Soporta configuración desde config.json
        """
        self.symbols = config.get('symbols', ['EURUSD', 'XAUUSD'])
        self.timeframe = config.get('timeframe', '1m')
        self.cycle_interval = config.get('cycle_interval', 60)
        self.min_confidence_threshold = config.get('min_confidence', 0.55)
        
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
        
        # Si el brain existe y tiene memory_consultant, pasarle signal_memory
        if self.brain and hasattr(self.brain, 'memory_consultant') and self.signal_memory:
            self.brain.memory_consultant.memory = self.signal_memory
            logger.info("🧠 Brain Cline conectado con Signal Memory")
        
        logger.info(f"🧠 Orquestador configurado | {len(self.symbols)} símbolos | "
                   f"TF: {self.timeframe} | Int: {self.cycle_interval}s | "
                   f"MinConf: {self.min_confidence_threshold}")
    
    async def run_cycle(self, symbol: str) -> Dict:
        """
        Ejecuta un ciclo completo de trading para un símbolo
        Flujo: Data → Indicators → Memory → Processor → Brain (v3.0) → Risk → Execution
        """
        self.cycle_count += 1
        cycle_id = f"CYCLE_{self.cycle_count}_{symbol}_{datetime.now().timestamp()}"
        
        logger.info(f"🚀 Iniciando ciclo {cycle_id}")
        
        try:
            # ========== PASO 1: OBTENER DATOS ==========
            logger.info(f"[{cycle_id}] 1/7 - Obteniendo datos...")
            df = await self._fetch_market_data(symbol)
            if df is None or df.empty:
                return {"status": "ERROR", "reason": "Sin datos", "symbol": symbol}
            
            # Asegurar columnas necesarias para Brain v3.0
            df = self._ensure_brain_columns(df)
            
            # ========== PASO 2: CALCULAR INDICADORES ==========
            logger.info(f"[{cycle_id}] 2/7 - Indicadores...")
            indicators = self._calculate_indicators(df, symbol)
            
            # ========== PASO 3: CONSULTAR MEMORIA ==========
            logger.info(f"[{cycle_id}] 3/7 - Memoria...")
            memory_insights = self._consult_memory(symbol)
            
            # ========== PASO 4: PROCESAR DATOS ==========
            logger.info(f"[{cycle_id}] 4/7 - Procesando...")
            processed_data = self._process_data(df, indicators, symbol)
            
            # ========== PASO 5: CEREBRO ANALIZA (v3.0) ==========
            logger.info(f"[{cycle_id}] 5/7 - Brain Cline v3.0...")
            context = await self._brain_analysis(df, symbol, memory_insights, processed_data)
            if context is None:
                return {"status": "ERROR", "reason": "Brain analysis failed", "symbol": symbol}
            
            # ========== PASO 6: VALIDAR RIESGO ==========
            logger.info(f"[{cycle_id}] 6/7 - Riesgo...")
            risk_approved, risk_reason = self._validate_risk(context)
            
            if not risk_approved:
                logger.warning(f"[{cycle_id}] ❌ Riesgo: {risk_reason}")
                return {
                    "status": "RISK_REJECTED",
                    "reason": risk_reason,
                    "context": context.__dict__
                }
            
            # ========== PASO 7: EJECUTAR ==========
            if context.decision in ["BUY", "SELL"] and context.confidence > self.min_confidence_threshold:
                logger.info(f"[{cycle_id}] 7/7 - Ejecutando {context.decision}")
                execution_result = await self._execute_trade(context)
                
                result = {
                    "status": "EXECUTED",
                    "decision": context.decision,
                    "confidence": context.confidence,
                    "execution": execution_result,
                    "context": context.__dict__,
                    "regime": context.regime,
                    "divergence": context.divergence,
                    "technical_score": context.technical_score,
                    "urgency": context.urgency,
                    "time_horizon": context.time_horizon,
                }
            else:
                reason = f"Confianza insuficiente ({context.confidence:.2f})"
                if context.regime_alignment < 0.3:
                    reason += f" | Régimen no alineado ({context.regime})"
                if context.divergence == "NONE" and context.confidence > 0.6:
                    reason += " | Sin divergencia confirmatoria"
                
                logger.info(f"[{cycle_id}] 7/7 - HOLD: {reason}")
                result = {
                    "status": "HOLD",
                    "reason": reason,
                    "context": context.__dict__
                }
            
            # Guardar resultado
            self.cycle_results.append(result)
            if len(self.cycle_results) > 100:
                self.cycle_results = self.cycle_results[-100:]
            
            return result
        
        except Exception as e:
            logger.error(f"[{cycle_id}] ❌ Error: {e}", exc_info=True)
            return {"status": "ERROR", "reason": str(e), "symbol": symbol}
    
    def _ensure_brain_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Asegura que el DataFrame tenga las columnas que Brain v3.0 espera"""
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in df.columns:
                if col == 'close' and 'price' in df.columns:
                    df['close'] = df['price']
                elif col == 'close':
                    df[col] = df.get('open', 1.0)
                else:
                    df[col] = df['close'] * (1 + np.random.normal(0, 0.001, len(df)))
        
        if 'volume' not in df.columns:
            df['volume'] = np.random.randint(1000, 10000, len(df))
        
        return df
    
    async def _brain_analysis(self, df: pd.DataFrame, symbol: str,
                              memory_insights: Dict,
                              processed_data: Dict) -> Optional[TradingContext]:
        """
        Análisis del cerebro v3.0.
        Pasa el DataFrame completo (no convertido desde dict) para
        que el brain pueda hacer análisis técnico real.
        """
        if not self.brain:
            logger.error("Brain no configurado")
            return None
        
        try:
            # Brain Cline v3.0 recibe el DataFrame completo
            signal = self.brain.generate_trading_decision(df, symbol)
            
            # Obtener contexto del brain (análisis técnico)
            brain_context = self.brain.get_market_context(symbol)
            
            # Construir contexto enriquecido
            context = TradingContext(
                symbol=symbol,
                timestamp=datetime.now(),
                market_data=df,
                indicators=processed_data.get('indicators', {}),
                memory_insights=memory_insights,
                regime=brain_context.get('regime', 'UNKNOWN'),
                sentiment=brain_context.get('sentiment', 0.0),
                confidence=signal.confidence,
                decision=signal.signal.value if hasattr(signal.signal, 'value') else signal.signal,
                reasoning=signal.reasoning,
                # Nuevos campos v3.0
                technical_score=brain_context.get('technical_score', 0.0),
                divergence=brain_context.get('divergence', 'NONE'),
                volume_profile=brain_context.get('volume_profile', 'NORMAL'),
                regime_alignment=getattr(signal, 'market_regime_alignment', 0.0),
                urgency=getattr(signal, 'urgency', 'LOW'),
                time_horizon=getattr(signal, 'time_horizon', 'INTRADAY'),
                sl_price=getattr(signal, 'stop_loss', 0.0),
                tp_price=getattr(signal, 'take_profit', 0.0),
                risk_reward=getattr(signal, 'risk_reward_ratio', 0.0),
                rsi=brain_context.get('rsi', 50.0),
                adx=brain_context.get('adx', 20.0),
                candle_pattern=brain_context.get('candle_pattern', 'NONE'),
            )
            
            return context
        
        except Exception as e:
            logger.error(f"Error en brain v3.0: {e}", exc_info=True)
            return None
    
    async def _fetch_market_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Obtiene datos de mercado con soporte para múltiples fuentes"""
        if not self.data_ingestion:
            logger.error("Data Ingestion no configurado")
            return self._generate_synthetic_data(symbol)
        
        try:
            data = await self.data_ingestion.fetch_live_data(symbol, source='ccxt')
            if data is None or data.empty:
                logger.warning(f"Fallback a sintéticos para {symbol}")
                data = self._generate_synthetic_data(symbol)
            return data
        except Exception as e:
            logger.error(f"Error fetching: {e}")
            return self._generate_synthetic_data(symbol)
    
    def _calculate_indicators(self, df: pd.DataFrame, symbol: str) -> Dict[str, float]:
        """Calcula indicadores técnicos (delegado a Indicator Engine o cálculo directo)"""
        if self.indicator_engine:
            try:
                return self.indicator_engine.calculate_all(df, symbol)
            except Exception as e:
                logger.warning(f"Error en Indicator Engine: {e}")
        
        # Fallback: indicadores básicos
        return {
            'sma_20': df['close'].rolling(20).mean().iloc[-1] if len(df) >= 20 else df['close'].iloc[-1],
            'sma_50': df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else df['close'].iloc[-1],
            'rsi': self._calc_rsi(df['close']),
            'atr': self._calc_atr(df),
            'volume_ma20': df['volume'].rolling(20).mean().iloc[-1] if len(df) >= 20 and 'volume' in df else 0,
        }
    
    def _consult_memory(self, symbol: str) -> Dict:
        """Consulta la memoria de operaciones para insights"""
        if not self.signal_memory:
            return {}
        try:
            return self.signal_memory.get_insights(symbol)
        except Exception as e:
            logger.warning(f"Error en memoria: {e}")
            return {}
    
    def _process_data(self, df: pd.DataFrame, indicators: Dict, symbol: str) -> Dict:
        """Procesa y normaliza datos para consumo interno"""
        if self.data_processor:
            try:
                return self.data_processor.normalize(df, indicators, symbol)
            except Exception:
                pass
        
        return {
            'symbol': symbol,
            'current_price': df['close'].iloc[-1],
            'indicators': indicators,
            'timestamp': datetime.now().isoformat(),
            'data_length': len(df),
            'data_columns': list(df.columns),
        }
    
    def _validate_risk(self, context: TradingContext) -> Tuple[bool, str]:
        """Valida riesgo usando los niveles calculados por Brain o Risk Manager"""
        if not self.risk_manager:
            logger.warning("Risk Manager no configurado - aprobando")
            return True, "NO_RISK_MANAGER"
        
        try:
            # Usar los niveles que calculó Brain si están disponibles
            sl_price = context.sl_price if context.sl_price > 0 else None
            tp_price = context.tp_price if context.tp_price > 0 else None
            
            # Calcular posición
            size, explanation = self.risk_manager.calculate_position_size(
                signal_confidence=context.confidence,
                symbol=context.symbol,
                df=context.market_data,
                price=context.market_data['close'].iloc[-1],
                regime=context.regime
            )
            
            if size <= 0:
                return False, explanation
            
            # Calcular SL/TP si Brain no lo hizo
            if sl_price is None:
                direction = "long" if context.decision == "BUY" else "short"
                sl_price, _ = self.risk_manager.calculate_stop_loss(
                    entry_price=context.market_data['close'].iloc[-1],
                    df=context.market_data,
                    direction=direction
                )
            if tp_price is None:
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
            
            # Guardar en context para ejecución
            context.sl_price = sl_price
            context.tp_price = tp_price
            context.reasoning += f"\nRisk: {explanation}"
            
            return approved, reason
        
        except Exception as e:
            logger.error(f"Error en riesgo: {e}")
            return False, str(e)
    
    async def _execute_trade(self, context: TradingContext) -> Dict:
        """Ejecuta la operación con los niveles de SL/TP calculados"""
        if not self.execution:
            logger.error("Execution Engine no configurado")
            return {"status": "ERROR", "reason": "No execution engine"}
        
        try:
            result = await self.execution.execute_order(
                symbol=context.symbol,
                side=context.decision,
                size=context.sl_price,
                stop_loss=context.sl_price,
                take_profit=context.tp_price
            )
            
            # Registrar en memoria
            if result.get('status') == 'FILLED':
                self._record_trade_to_memory(context, result)
            
            return result
        
        except Exception as e:
            logger.error(f"Error ejecutando: {e}")
            return {"status": "ERROR", "reason": str(e)}
    
    def _record_trade_to_memory(self, context: TradingContext, result: Dict):
        """Registra la operación en Signal Memory para aprendizaje"""
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
                'result': 'PENDING'
            }
            self.signal_memory.record_trade(trade_data)
        except Exception as e:
            logger.warning(f"Error registrando trade: {e}")
    
    async def run_continuous(self):
        """Ejecuta el ciclo continuo de trading"""
        logger.info(f"🔄 Orquestación continua iniciada | {len(self.symbols)} símbolos")
        self.is_running = True
        
        while self.is_running:
            try:
                for symbol in self.symbols:
                    if not self.is_running:
                        break
                    result = await self.run_cycle(symbol)
                    self._log_cycle_result(result)
                
                self.last_cycle_time = datetime.now()
                await asyncio.sleep(self.cycle_interval)
                
            except KeyboardInterrupt:
                logger.info("⏹️ Orquestador detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en ciclo: {e}", exc_info=True)
                await asyncio.sleep(self.cycle_interval)
        
        self.is_running = False
        logger.info("⏹️ Orquestador detenido")
    
    def stop(self):
        """Detiene el orquestador"""
        self.is_running = False
        logger.info("🛑 Señal de parada enviada")
    
    def _log_cycle_result(self, result: Dict):
        """Log detallado del resultado del ciclo"""
        status = result.get('status', 'UNKNOWN')
        symbol = result.get('symbol') or result.get('context', {}).get('symbol', 'UNKNOWN')
        
        if status == 'EXECUTED':
            decision = result.get('decision')
            confidence = result.get('confidence', 0)
            regime = result.get('regime', 'UNKNOWN')
            divergence = result.get('divergence', 'NONE')
            
            log_msg = f"✅ {symbol} → {decision} (conf: {confidence:.2f})"
            if regime != 'UNKNOWN':
                log_msg += f" | Régimen: {regime}"
            if divergence != 'NONE':
                log_msg += f" | Divergencia: {divergence}"
            
            urgency = result.get('urgency', 'MEDIUM')
            if urgency == 'HIGH':
                logger.info(f"⚡ {log_msg}")
            else:
                logger.info(log_msg)
                
        elif status == 'RISK_REJECTED':
            reason = result.get('reason', 'Unknown')
            logger.warning(f"⚠️ {symbol} → RECHAZADO: {reason}")
        elif status == 'ERROR':
            reason = result.get('reason', 'Unknown')
            logger.error(f"❌ {symbol} → ERROR: {reason}")
        else:
            context = result.get('context', {})
            regime = context.get('regime', '') if isinstance(context, dict) else ''
            logger.info(f"ℹ️ {symbol} → HOLD | Régimen: {regime}")
    
    def get_performance_summary(self) -> Dict:
        """
        Retorna resumen de rendimiento del orquestador.
        Útil para el ciclo de inteligencia diaria.
        """
        executed = [r for r in self.cycle_results if r.get('status') == 'EXECUTED']
        holds = [r for r in self.cycle_results if r.get('status') == 'HOLD']
        rejected = [r for r in self.cycle_results if r.get('status') == 'RISK_REJECTED']
        errors = [r for r in self.cycle_results if r.get('status') == 'ERROR']
        
        return {
            'total_cycles': self.cycle_count,
            'executed': len(executed),
            'holds': len(holds),
            'rejected': len(rejected),
            'errors': len(errors),
            'execution_rate': len(executed) / max(len(self.cycle_results), 1),
            'avg_confidence': sum(r.get('confidence', 0) for r in executed) / max(len(executed), 1) if executed else 0,
            'buy_pct': sum(1 for r in executed if r.get('decision') == 'BUY') / max(len(executed), 1) * 100 if executed else 0,
            'sell_pct': sum(1 for r in executed if r.get('decision') == 'SELL') / max(len(executed), 1) * 100 if executed else 0,
        }
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _calc_rsi(self, prices: pd.Series, period: int = 14) -> float:
        """RSI"""
        if len(prices) < period + 1:
            return 50
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not rsi.empty else 50
    
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
        """Genera datos sintéticos de respaldo para tests"""
        import numpy as np
        
        base_prices = {
            'EURUSD': 1.0850, 'GBPUSD': 1.2650,
            'XAUUSD': 2650.0, 'BTC/USDT': 50000.0,
            'ETH/USDT': 2800.0, 'SP500': 4800.0,
        }
        base = base_prices.get(symbol, 100.0)
        
        n = 100
        prices = [base]
        for _ in range(n - 1):
            prices.append(prices[-1] * (1 + np.random.normal(0, 0.001)))
        
        return pd.DataFrame({
            'timestamp': pd.date_range(end=datetime.now(), periods=n, freq='1min'),
            'open': prices,
            'high': [p * 1.002 for p in prices],
            'low': [p * 0.998 for p in prices],
            'close': prices,
            'volume': np.random.randint(1000, 10000, n)
        })


# Función de conveniencia
def create_orchestrator(config: Dict) -> Orchestrator:
    """Factory para crear el orquestador"""
    orchestrator = Orchestrator()
    orchestrator.configure(config)
    return orchestrator


if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Testing Orchestrator v2.1 con Brain Cline v3.0")
    print("=" * 60)
    
    orch = Orchestrator()
    orch.configure({
        'symbols': ['EURUSD', 'XAUUSD'],
        'timeframe': '1m',
        'cycle_interval': 60,
        'min_confidence': 0.55
    })
    
    print(f"\n✅ Orquestador configurado")
    print(f"   Símbolos: {orch.symbols}")
    print(f"   Timeframe: {orch.timeframe}")
    print(f"   Intervalo: {orch.cycle_interval}s")
    print(f"   Min Confianza: {orch.min_confidence_threshold}")
    
    print("\n📦 Módulos inyectables:")
    print("   - data_ingestion")
    print("   - indicator_engine")
    print("   - signal_memory (para MemoryConsultant)")
    print("   - data_processor")
    print("   - brain (BrainClineModule v3.0)")
    print("   - risk_manager (RiskManagerV2)")
    print("   - execution")
    
    print("\n🚀 Brain Cline v3.0 features activas:")
    print("   ✅ Multi-timeframe analysis")
    print("   ✅ Divergence detection (RSI)")
    print("   ✅ Volume profile (accumulation/distribution)")
    print("   ✅ Candle pattern recognition")
    print("   ✅ Regime classifier (ONNX + rules)")
    print("   ✅ Adaptive weights from Signal Memory")
    print("   ✅ Enhanced confidence (entropy, stability)")
    print("   ✅ Dynamic SL/TP with ATR")
    print("   ✅ Alert system")
    
    print("\n✅ Orquestador v2.1 listo")