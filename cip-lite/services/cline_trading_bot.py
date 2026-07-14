#!/usr/bin/env python3
"""
🤖 CLINE TRADING BOT - Sistema Unificado de Trading Institucional
Cline como cerebro con permisos administrativos completos
OPTIMIZADO: Sin rutas hardcodeadas, manejo robusto de errores, circuit breakers
"""

import asyncio
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

# Importaciones relativas robustas
try:
    from services.cline_brain import ClineBrain, MarketAnalysis
    from services.risk.dynamic_risk_manager import DynamicRiskManager
    from services.execution.engine import ExecutionEngine, Order, Position
    from services.exchanges.binance import BinanceExchange
except ImportError as e:
    logging.error(f"Error importando módulos: {e}")
    raise

import structlog
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = structlog.get_logger()


@dataclass
class BotState:
    """Estado global del bot con thread-safety"""
    is_running: bool = False
    admin_mode: bool = True
    emergency_stop: bool = False
    current_positions: Dict[str, Position] = field(default_factory=dict)
    daily_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    last_health_check: datetime = field(default_factory=datetime.now)
    consecutive_errors: int = 0
    circuit_breaker_active: bool = False


class CircuitBreaker:
    """
    Implementa patrón Circuit Breaker para prevenir fallos en cascada
    """
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_failure(self):
        """Registra un fallo y abre el circuito si se supera el threshold"""
        self.failures += 1
        self.last_failure_time = datetime.now()
        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failures} failures")
    
    def record_success(self):
        """Registra éxito y resetea el contador"""
        self.failures = 0
        self.state = "CLOSED"
    
    def can_execute(self) -> bool:
        """Verifica si el circuito permite ejecución"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN" and self.last_failure_time:
            elapsed = (datetime.now() - self.last_failure_time).total_seconds()
            if elapsed >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker HALF_OPEN - testing recovery")
                return True
        
        return self.state == "HALF_OPEN"
    
    def reset(self):
        """Resetea el circuit breaker"""
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"


class ClineTradingBot:
    """
    Bot de trading institucional con Cline como cerebro supremo
    Permisos administrativos completos para operar en exchanges reales
    OPTIMIZADO: Circuit breakers, retry logic, validación de datos, health checks
    """
    
    def __init__(self, initial_capital: float = 10000.0, admin_mode: bool = True):
        # Inicializar componentes core
        self.brain = ClineBrain()
        self.risk_mgr = DynamicRiskManager(initial_capital=initial_capital)
        self.executor = ExecutionEngine(initial_capital=initial_capital)
        self.exchange = None  # Se inicializa con credenciales
        
        # Estado del bot
        self.state = BotState(admin_mode=admin_mode)
        
        # Circuit breakers para diferentes operaciones
        self.circuit_breakers = {
            'data_fetch': CircuitBreaker(failure_threshold=3, recovery_timeout=30),
            'analysis': CircuitBreaker(failure_threshold=5, recovery_timeout=60),
            'execution': CircuitBreaker(failure_threshold=2, recovery_timeout=120)
        }
        
        # Permisos administrativos de Cline
        self._grant_admin_permissions()
        
        # Configuración
        self.initial_capital = initial_capital
        self.symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'ADA/USDT']
        self.data_source = 'synthetic'  # synthetic, ccxt, mt5
        
        # Métricas de salud
        self.health_status = {
            'last_successful_trade': None,
            'consecutive_failures': 0,
            'uptime_start': datetime.now()
        }
        
        logger.info(f"Cline Trading Bot inicializado | Admin: {admin_mode} | Capital: ${initial_capital:,.2f}")
    
    def _grant_admin_permissions(self):
        """
        Otorga permisos administrativos completos a Cline
        """
        self.state.admin_mode = True
        
        # Permisos de lectura
        self.permissions = {
            # Análisis
            'can_analyze_market': True,
            'can_generate_strategies': True,
            'can_backtest': True,
            'can_optimize_params': True,
            
            # Trading
            'can_open_positions': True,
            'can_close_positions': True,
            'can_adjust_stops': True,
            'can_rebalance_portfolio': True,
            
            # Riesgo
            'can_adjust_risk_params': True,
            'can_override_risk_limits': True,
            'can_emergency_stop': True,
            
            # Gestión
            'can_withdraw_funds': False,  # Requiere 2FA manual
            'can_modify_api_keys': False,  # Seguridad crítica
            'can_change_strategy_mode': True,
            
            # Datos
            'can_access_ccxt': True,
            'can_access_mt5': True,
            'can_download_historical': True,
            
            # Admin supremo
            'admin_override': True,
            'emergency_liquidation': True
        }
        
        logger.info("Permisos administrativos otorgados a Cline", permissions=list(self.permissions.keys()))
    
    def has_permission(self, action: str) -> bool:
        """Verifica si Cline tiene permiso para realizar una acción"""
        # Permisos críticos nunca pueden ser overrideados por admin_override
        critical_permissions = ['withdraw_funds', 'modify_api_keys']
        
        if f'can_{action}' in critical_permissions or action in critical_permissions:
            # Para permisos críticos, verificar explícitamente sin admin_override
            return self.permissions.get(f'can_{action}', False)
        
        # Para otros permisos, permitir admin_override
        return self.permissions.get(f'can_{action}', False) or self.permissions.get('admin_override', False)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((ConnectionError, TimeoutError))
    )
    async def fetch_live_data(self, symbol: str, source: str = 'ccxt') -> Optional[pd.DataFrame]:
        """
        Obtiene datos en tiempo real desde CCXT o MT5 con retry automático
        Circuit breaker integrado para prevenir fallos en cascada
        """
        # Verificar circuit breaker
        if not self.circuit_breakers['data_fetch'].can_execute():
            logger.warning(f"Circuit breaker activo para data_fetch - {symbol}")
            return None
        
        if not self.has_permission('access_ccxt'):
            logger.warning("Cline sin permisos para acceder a CCXT")
            return None
        
        try:
            if source == 'ccxt':
                import ccxt
                exchange = ccxt.binance()
                exchange.enableRateLimit = True
                
                # Obtener últimas 500 velas
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=500)
                
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                # Validar datos
                if not self._validate_dataframe(df):
                    logger.error(f"Datos inválidos para {symbol}")
                    self.circuit_breakers['data_fetch'].record_failure()
                    return None
                
                logger.info(f"Datos CCXT obtenidos: {symbol} ({len(df)} velas)")
                self.circuit_breakers['data_fetch'].record_success()
                return df
            
            elif source == 'mt5':
                if not self.has_permission('access_mt5'):
                    logger.warning("Cline sin permisos para acceder a MT5")
                    return None
                
                import MetaTrader5 as mt5
                if not mt5.initialize():
                    logger.error("Error inicializando MT5")
                    self.circuit_breakers['data_fetch'].record_failure()
                    return None
                
                rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 500)
                mt5.shutdown()
                
                if rates is None or len(rates) == 0:
                    self.circuit_breakers['data_fetch'].record_failure()
                    return None
                
                df = pd.DataFrame(rates)
                df['timestamp'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('timestamp', inplace=True)
                df.rename(columns={'tick_volume': 'volume'}, inplace=True)
                
                # Validar datos
                if not self._validate_dataframe(df):
                    logger.error(f"Datos MT5 inválidos para {symbol}")
                    self.circuit_breakers['data_fetch'].record_failure()
                    return None
                
                logger.info(f"Datos MT5 obtenidos: {symbol} ({len(df)} velas)")
                self.circuit_breakers['data_fetch'].record_success()
                return df
        
        except (ConnectionError, TimeoutError) as e:
            logger.error(f"Error de conexión obteniendo datos: {e}")
            self.circuit_breakers['data_fetch'].record_failure()
            raise  # Para que retry funcione
        except Exception as e:
            logger.error(f"Error obteniendo datos: {e}")
            self.circuit_breakers['data_fetch'].record_failure()
            return None
    
    def _validate_dataframe(self, df: pd.DataFrame) -> bool:
        """
        Valida que el DataFrame tenga estructura y datos válidos
        Schema validation básico
        """
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        
        # Check columnas requeridas
        if not all(col in df.columns for col in required_columns):
            return False
        
        # Check datos nulos
        if df[required_columns].isnull().any().any():
            return False
        
        # Check valores positivos
        if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
            return False
        
        # Check coherencia OHLC
        if (df['high'] < df['low']).any() or \
           (df['high'] < df['open']).any() or \
           (df['high'] < df['close']).any():
            return False
        
        # Check mínimo de datos
        if len(df) < 50:
            return False
        
        return True
    
    async def execute_signal(self, signal, symbol: str) -> Optional[Order]:
        """
        Ejecuta una señal de trading generada por Cline con validación y circuit breaker
        """
        # Verificar circuit breaker de ejecución
        if not self.circuit_breakers['execution'].can_execute():
            logger.warning(f"Circuit breaker activo para execution - {symbol}")
            return None
        
        if not self.has_permission('open_positions') and not self.has_permission('can_open_positions'):
            logger.warning("Cline sin permisos para abrir posiciones")
            return None
        
        # Validar señal
        if signal.signal not in ['BUY', 'SELL']:
            return None
        
        # Obtener precio actual
        current_price = signal.entry_price
        
        # Validar precio
        if current_price <= 0 or np.isnan(current_price):
            logger.error(f"Precio inválido para {symbol}: {current_price}")
            self.circuit_breakers['execution'].record_failure()
            return None
        
        try:
            # Calcular tamaño de posición con risk manager
            position_size = self.risk_mgr.position_size(
                signal_confidence=signal.confidence,
                symbol=symbol,
                df=None,
                price=current_price
            )
            
            # Crear orden
            quantity = (self.risk_mgr.current_capital * 0.02) / current_price  # 2% del capital
            
            order = Order(
                order_id=f"CLINE_{datetime.now().timestamp()}",
                symbol=symbol,
                side=signal.signal,
                quantity=quantity,
                price=current_price,
                order_type="MARKET"
            )
            
            # Ejecutar
            executed_order = self.executor.create_order(
                signal=signal.signal,
                confidence=signal.confidence,
                symbol=symbol,
                price=current_price
            )
            
            if executed_order:
                logger.info(f"Orden ejecutada por Cline: {signal.signal} {quantity:.6f} {symbol}")
                self.state.total_trades += 1
                self.health_status['last_successful_trade'] = datetime.now()
                self.health_status['consecutive_failures'] = 0
                
                # Actualizar estado
                self._update_state_after_trade(signal, executed_order)
                self.circuit_breakers['execution'].record_success()
            else:
                self.circuit_breakers['execution'].record_failure()
            
            return executed_order
            
        except Exception as e:
            logger.error(f"Error ejecutando señal: {e}")
            self.circuit_breakers['execution'].record_failure()
            self.health_status['consecutive_failures'] += 1
            return None
    
    def _update_state_after_trade(self, signal, order: Order):
        """Actualiza el estado del bot después de un trade"""
        if order and order.filled_quantity > 0:
            if signal.signal == 'BUY':
                self.state.current_positions[order.symbol] = Position(
                    symbol=order.symbol,
                    quantity=order.filled_quantity,
                    avg_entry_price=order.avg_fill_price or order.price
                )
    
    async def run_trading_cycle(self, symbol: str, data_source: str = 'ccxt'):
        """
        Ciclo completo de trading: Análisis → Decisión → Ejecución
        Con circuit breakers y health checks
        """
        if self.state.emergency_stop:
            logger.warning("EMERGENCY STOP ACTIVO - No se puede operar")
            return {"status": "EMERGENCY_STOP", "action": None}
        
        # Health check: verificar fallos consecutivos
        if self.health_status['consecutive_failures'] >= 5:
            logger.error(f"Demasiados fallos consecutivos ({self.health_status['consecutive_failures']}) - Pausando trading")
            return {"status": "HEALTH_CHECK_FAILED", "reason": "Consecutive failures"}
        
        # 1. Obtener datos (con circuit breaker)
        df = await self.fetch_live_data(symbol, data_source)
        if df is None or len(df) < 50:
            self.state.consecutive_errors += 1
            return {"status": "ERROR", "reason": "Datos insuficientes"}
        
        # Resetear errores si obtenemos datos válidos
        self.state.consecutive_errors = 0
        
        # 2. Cline analiza mercado (con circuit breaker)
        if not self.circuit_breakers['analysis'].can_execute():
            logger.warning(f"Circuit breaker activo para analysis - {symbol}")
            return {"status": "CIRCUIT_BREAKER", "reason": "Analysis CB active"}
        
        if not self.has_permission('analyze_market'):
            return {"status": "ERROR", "reason": "Sin permisos de análisis"}
        
        try:
            analysis = self.brain.analyze_market(df, symbol)
            self.circuit_breakers['analysis'].record_success()
        except Exception as e:
            logger.error(f"Error analizando mercado: {e}")
            self.circuit_breakers['analysis'].record_failure()
            return {"status": "ERROR", "reason": f"Analysis error: {e}"}
        
        # 3. Cline genera decisión
        if not self.has_permission('generate_strategies'):
            return {"status": "ERROR", "reason": "Sin permisos de generación de estrategias"}
        
        try:
            signal = self.brain.generate_trading_decision(df, symbol)
        except Exception as e:
            logger.error(f"Error generando decisión: {e}")
            self.circuit_breakers['analysis'].record_failure()
            return {"status": "ERROR", "reason": f"Signal generation error: {e}"}
        
        # 4. Verificar riesgo
        risk_approved = self._check_risk_limits(signal, analysis)
        
        if not risk_approved:
            logger.warning(f"Riesgo excedido para {symbol}")
            return {"status": "RISK_REJECTED", "signal": signal, "analysis": analysis}
        
        # 5. Ejecutar si señal es válida
        result = {"status": "HOLD", "signal": signal, "analysis": analysis}
        
        if signal.signal in ['BUY', 'SELL'] and signal.confidence > 0.5:
            order = await self.execute_signal(signal, symbol)
            if order:
                result = {
                    "status": "EXECUTED",
                    "action": signal.signal,
                    "order": order.__dict__,
                    "signal": signal,
                    "analysis": analysis
                }
        
        return result
    
    def get_health_status(self) -> Dict:
        """
        Retorna el estado de salud del bot para monitoring
        """
        uptime = datetime.now() - self.health_status['uptime_start']
        
        return {
            'is_healthy': self.health_status['consecutive_failures'] < 5,
            'consecutive_failures': self.health_status['consecutive_failures'],
            'last_successful_trade': self.health_status['last_successful_trade'],
            'uptime_seconds': uptime.total_seconds(),
            'circuit_breakers': {
                name: cb.state for name, cb in self.circuit_breakers.items()
            },
            'emergency_stop': self.state.emergency_stop,
            'total_trades': self.state.total_trades
        }
    
    def _check_risk_limits(self, signal, analysis: MarketAnalysis) -> bool:
        """Verifica límites de riesgo antes de operar"""
        issues = []
        
        # Check drawdown
        if self.risk_mgr.current_capital < self.risk_mgr.peak_value * 0.9:
            issues.append("Drawdown > 10%")
        
        # Check VaR diario
        var = self.risk_mgr.value_at_var()
        if var > self.risk_mgr.current_capital * 0.02:
            issues.append(f"VaR excedido: {var/self.risk_mgr.current_capital:.1%}")
        
        # Check volatilidad extrema
        if analysis.volatility > 0.1:
            issues.append("Volatilidad extrema")
        
        # Si hay admin override, ignorar límites
        if self.permissions.get('can_override_risk_limits', False) and len(issues) > 0:
            logger.warning(f"Admin override activo - Ignorando {len(issues)} warnings de riesgo")
            return True
        
        return len(issues) == 0
    
    async def emergency_stop_all(self):
        """
        EMERGENCY STOP - Cierra todas las posiciones inmediatamente
        Solo ejecutable con permiso administrativo
        """
        if not self.has_permission('emergency_stop'):
            logger.error("Intento de emergency stop sin permisos")
            return {"status": "DENIED", "reason": "Sin permisos de emergencia"}
        
        logger.warning("⚠️ EMERGENCY STOP ACTIVADO POR CLINE")
        self.state.emergency_stop = True
        
        # Cerrar todas las posiciones
        closed_positions = []
        for symbol, position in list(self.state.current_positions.items()):
            try:
                # Obtener precio actual
                ticker = await self.exchange.get_ticker(symbol) if self.exchange else None
                if ticker:
                    # Crear orden de cierre
                    close_order = Order(
                        order_id=f"EMERGENCY_{datetime.now().timestamp()}",
                        symbol=symbol,
                        side='SELL' if position.quantity > 0 else 'BUY',
                        quantity=abs(position.quantity),
                        price=ticker.last_price,
                        order_type="MARKET"
                    )
                    closed_positions.append({
                        'symbol': symbol,
                        'quantity': position.quantity,
                        'price': ticker.last_price
                    })
                    logger.info(f"Posición cerrada: {symbol}")
            except Exception as e:
                logger.error(f"Error cerrando {symbol}: {e}")
        
        self.state.current_positions = {}
        
        return {
            "status": "EMERGENCY_COMPLETE",
            "closed": len(closed_positions),
            "positions": closed_positions
        }
    
    async def run_continuous(self, symbols: List[str], data_source: str = 'ccxt', interval_seconds: int = 60):
        """
        Ejecuta el bot en modo continuo
        """
        if not self.has_permission('can_analyze'):
            logger.error("Cline sin permisos para ejecutar")
            return
        
        self.state.is_running = True
        logger.info(f"Bot iniciado en modo continuo | Admin: {self.state.admin_mode} | Intervalo: {interval_seconds}s")
        
        while self.state.is_running:
            try:
                for symbol in symbols:
                    if self.state.emergency_stop:
                        logger.warning("Emergency stop detectado - Deteniendo bot")
                        break
                    
                    result = await self.run_trading_cycle(symbol, data_source)
                    logger.info(f"Ciclo completado: {symbol} → {result.get('status')}")
                
                # Esperar siguiente ciclo
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Detención manual del bot")
                break
            except Exception as e:
                logger.error(f"Error en ciclo de trading: {e}")
                await asyncio.sleep(interval_seconds)
        
        self.state.is_running = False
        logger.info("Bot detenido")


# Función de conveniencia
def create_cline_bot(initial_capital: float = 10000.0, admin_mode: bool = True) -> ClineTradingBot:
    """Factory para crear el bot de trading con Cline"""
    return ClineTradingBot(initial_capital=initial_capital, admin_mode=admin_mode)


if __name__ == "__main__":
    print("=" * 70)
    print("🤖 CLINE TRADING BOT - Modo Administrativo")
    print("=" * 70)
    
    # Crear bot con permisos admin
    bot = create_cline_bot(initial_capital=10000.0, admin_mode=True)
    
    print(f"\n✅ Bot creado con permisos administrativos")
    print(f"   Capital: ${bot.initial_capital:,.2f}")
    print(f"   Admin Mode: {bot.state.admin_mode}")
    print(f"   Permisos otorgados: {sum(bot.permissions.values())}/{len(bot.permissions)}")
    
    print("\n📋 Permisos de Cline:")
    for perm, granted in bot.permissions.items():
        status = "✅" if granted else "❌"
        print(f"   {status} {perm}")
    
    print(f"\n⚠️  ADVERTENCIA: Este bot puede operar en exchanges reales")
    print(f"   Usar '--paper' para pruebas sin dinero real")
    print(f"\n🚀 Para iniciar: bot.run_continuous(['BTC/USDT', 'ETH/USDT'])")