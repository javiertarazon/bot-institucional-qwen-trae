"""
MCP Server para CIP-Lite v3.0
Exponer herramientas para Cline actuar como agente autónomo de scalping
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Optional
import structlog

# Agregar path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("⚠️ MCP no disponible. Instalar: pip install mcp")

logger = structlog.get_logger()


if MCP_AVAILABLE:
    mcp = FastMCP("CIP-Lite-Prop-Scalper")
    
    # Componentes (se inicializarán lazy)
    _micro_engine = None
    _whale_tracker = None
    _brain = None
    _risk_mgr = None
    
    def _get_components():
        """Lazy initialization de componentes"""
        global _micro_engine, _whale_tracker, _brain, _risk_mgr
        
        if _micro_engine is None:
            from src.modules.microstructure_engine.engine import MicrostructureEngine
            _micro_engine = MicrostructureEngine()
        
        if _whale_tracker is None:
            from src.modules.microstructure_engine.whale_tracker import WhaleTracker
            _whale_tracker = WhaleTracker()
        
        if _brain is None:
            from src.modules.microstructure_engine.brain_adapter import get_brain_adapter
            _brain = get_brain_adapter()
        
        if _risk_mgr is None:
            from risk_manager import RiskManagerV2
            _risk_mgr = RiskManagerV2(initial_capital=500.0)
        
        return _micro_engine, _whale_tracker, _brain, _risk_mgr


    @mcp.tool()
    async def get_scalping_state(symbol: str) -> dict:
        """
        Obtiene el estado de microestructura y la señal del ML en tiempo real.
        Es el punto de entrada principal para Cline.
        """
        micro, whale, brain, risk = _get_components()
        
        # Placeholder: en producción usar CCXT Pro para datos en tiempo real
        # Aquí usar datos históricos como demostración
        import pandas as pd
        import numpy as np
        
        # Generar datos sintéticos para demo
        df = pd.DataFrame({
            'open': [1.0] * 50,
            'high': [1.002] * 50,
            'low': [0.998] * 50,
            'close': [1.0 + np.random.normal(0, 0.001, 50).cumsum() * 0.0001],
            'volume': np.random.randint(1000, 10000, 50)
        })
        
        # Obtener análisis del brain
        if brain:
            analysis = brain.analyze_market(df, symbol)
            ml_signal = analysis.trend if analysis else "NEUTRAL"
            confidence = analysis.confidence if analysis else 0.5
        else:
            ml_signal = "NEUTRAL"
            confidence = 0.5
        
        return {
            "symbol": symbol,
            "ml_signal": ml_signal,
            "confidence": confidence,
            "account_status": risk.get_metrics().__dict__ if risk else {},
            "timestamp": str(pd.Timestamp.now())
        }
    
    @mcp.tool()
    async def execute_prop_scalp(symbol: str, side: str, confidence: float, 
                                  sl_pct: float = 0.5) -> dict:
        """
        Ejecuta orden optimizada para Prop Firms.
        Usa órdenes LIMIT (Post-Only) para evitar fees de Taker.
        """
        micro, whale, brain, risk = _get_components()
        
        # Verificar circuit breaker
        if risk and not risk.can_trade():
            return {"error": "Circuit breaker activado. Drawdown diario excedido."}
        
        # Calcular tamaño con Fractional Kelly
        # (simplificado - en producción usar cálculo completo)
        size_usd = 10.0 * confidence  # Simplificado
        
        return {
            "status": "ORDER_PLACED",
            "symbol": symbol,
            "side": side,
            "size_usd": size_usd,
            "order_type": "LIMIT_POST_ONLY",
            "note": "Simulado - integrar con CCXT en producción"
        }
    
    @mcp.tool()
    async def get_market_microstructure(symbol: str) -> dict:
        """
        Obtiene datos de microestructura en tiempo real.
        Requiere integración con CCXT Pro WebSocket.
        """
        return {
            "symbol": symbol,
            "best_bid": 1.0,
            "best_ask": 1.001,
            "spread_bps": 1.0,
            "order_book_imbalance": 1.5,
            "cvd_1m": 0.0,
            "note": "Placeholder - integrar con datos reales vía WS"
        }
    
    def run_server():
        """Ejecuta el servidor MCP"""
        mcp.run()


# Función de conveniencia para testing
def get_mcp_tools() -> list:
    """Retorna lista de herramientas MCP disponibles"""
    return ["get_scalping_state", "execute_prop_scalp", "get_market_microstructure"]


if __name__ == "__main__":
    if MCP_AVAILABLE:
        print("🚀 MCP Server listo - CIP-Lite Prop Scalper")
        print(f"   Herramientas: {get_mcp_tools()}")
        print("\nEjecutar: python mcp_server/server.py")
    else:
        print("⚠️  Instalar MCP: pip install mcp")