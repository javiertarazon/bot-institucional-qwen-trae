"""
Macro Filter - Filtro de eventos macroeconómicos
Evita operar durante eventos de alto impacto (CPI, FOMC, NFP)
"""

import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional
import structlog

logger = structlog.get_logger()


class MacroFilter:
    """
    Filtra operaciones basándose en eventos macroeconómicos.
    Adaptación de bajo recurso para scalping.
    """
    
    def __init__(self, api_url: Optional[str] = None):
        self.blackout_window_minutes = 15
        # API gratuita: Forex Factory, Investing.com, o TradingEconomics
        self.api_url = api_url or "https://cdn-nfs.faireconomy.media"  # API alternativa
        self.cache: Optional[Dict] = None
        self.cache_expiry: Optional[datetime] = None
    
    async def is_safe_to_trade(self, symbols: Optional[list] = None) -> Dict:
        """
        Verifica si hay eventos macroeconómicos de alto impacto.
        
        Returns:
            {"safe": bool, "reason": str, "events": list}
        """
        now = datetime.now()
        
        # Check cache (1 minuto)
        if self.cache and self.cache_expiry and now < self.cache_expiry:
            return self.cache
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # API simplificada - en producción usar calendario económico real
                # Por ejemplo: https://api.tradingeconomics.com/calendar
                response = await client.get(
                    f"{self.api_url}/api/economic_calendar.json",
                    params={"impact": "high", "hours": 1}
                )
                
                if response.status_code == 200:
                    events = response.json()
                    
                    # Filtrar eventos próximos (15 min)
                    upcoming_events = []
                    for event in events.get('events', []):
                        event_time = datetime.fromisoformat(event.get('timestamp', ''))
                        time_diff = (event_time - now).total_seconds() / 60
                        if 0 <= time_diff <= self.blackout_window_minutes:
                            upcoming_events.append(event)
                    
                    if upcoming_events:
                        self.cache = {
                            "safe": False,
                            "reason": f"Evento macroeconómico inminente: {upcoming_events[0].get('title', 'Unknown')}",
                            "events": upcoming_events
                        }
                    else:
                        self.cache = {
                            "safe": True,
                            "reason": "Sin eventos macro de alto impacto",
                            "events": []
                        }
                else:
                    # Si falla la API, asumir seguro
                    logger.warning(f"API falló: {response.status_code}")
                    self.cache = {"safe": True, "reason": "API no disponible - operando"}
                
                self.cache_expiry = now + timedelta(minutes=1)
                return self.cache
                
        except Exception as e:
            logger.warning(f"Error en macro filter: {e}")
            # Fallback: operar igual (mejor pérdida por noticia que pérdida por no operar)
            return {"safe": True, "reason": "API no disponible - asumiendo seguro"}


# Singleton
_macro_filter_instance = None

def get_macro_filter() -> MacroFilter:
    """Factory singleton para Macro Filter"""
    global _macro_filter_instance
    if _macro_filter_instance is None:
        _macro_filter_instance = MacroFilter()
    return _macro_filter_instance