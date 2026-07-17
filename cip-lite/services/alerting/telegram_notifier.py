"""
Telegram Notifier - Sistema de alertas para monitoreo del bot
Notifica trades, circuit breakers y eventos críticos
"""

import httpx
from typing import Optional
import structlog
import os

logger = structlog.get_logger()


class TelegramAlerts:
    """
    Sistema de alertas ligero para monitoreo institucional.
    Usa la API gratuita de Telegram.
    """
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        self.bot_token = bot_token or os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID', '')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
    
    async def send_alert(self, message: str, level: str = "INFO") -> bool:
        """
        Envía una alerta a Telegram.
        
        Args:
            message: Texto del mensaje
            level: INFO, WARNING, CRITICAL, TRADE
        """
        if not self.base_url:
            logger.debug(f"[ALERTA] {message}")
            return True  # Log local si no hay token
        
        emojis = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "CRITICAL": "🚨",
            "TRADE": "💰"
        }
        emoji = emojis.get(level, "📌")
        text = f"{emoji} *CIP-Lite v3.0 [{level}]*\n\n{message}"
        
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/sendMessage",
                    json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"},
                    timeout=5.0
                )
            return True
        except Exception as e:
            logger.error(f"Error enviando alerta Telegram: {e}")
            return False
    
    async def notify_circuit_breaker(self, reason: str, drawdown_pct: float):
        """Notifica cuando se activa el circuit breaker"""
        msg = f"*CIRCUIT BREAKER ACTIVADO*\n\nRazón: {reason}\nDrawdown: {drawdown_pct:.2f}%"
        await self.send_alert(msg, level="CRITICAL")
    
    async def notify_trade_execution(self, symbol: str, side: str, entry: float, 
                                     sl: float, tp: float, confidence: float = 0.0):
        """Notifica cuando se ejecuta una operación"""
        msg = (f"*NUEVA OPERACIÓN*\n\n"
               f"Par: {symbol}\n"
               f"Dirección: {side}\n"
               f"Entrada: ${entry:.2f}\n"
               f"SL: ${sl:.2f}\n"
               f"TP: ${tp:.2f}\n"
               f"Confianza: {confidence:.1%}")
        await self.send_alert(msg, level="TRADE")
    
    async def notify_trade_closed(self, symbol: str, pnl: float, reason: str):
        """Notifica cuando se cierra una operación"""
        emoji = "📈" if pnl > 0 else "📉"
        msg = f"{emoji} *OPERACIÓN CERRADA*\n\n{symbol} | P&L: ${pnl:+.2f} | {reason}"
        level = "TRADE" if pnl > 0 else "WARNING"
        await self.send_alert(msg, level=level)
    
    async def notify_error(self, error: str, symbol: str = "SYSTEM"):
        """Notifica errores del sistema"""
        msg = f"*ERROR*\n\nSímbolo: {symbol}\nError: {error[:200]}"
        await self.send_alert(msg, level="CRITICAL")


# Singleton
_telegram_instance = None

def get_telegram_notifier(bot_token: Optional[str] = None, 
                         chat_id: Optional[str] = None) -> TelegramAlerts:
    """Factory singleton para Telegram Notifier"""
    global _telegram_instance
    if _telegram_instance is None:
        _telegram_instance = TelegramAlerts(bot_token, chat_id)
    return _telegram_instance


# Función de conveniencia sync
def send_quick_alert(message: str, level: str = "INFO"):
    """Envía alerta sin async (para uso en threads)"""
    import asyncio
    notifier = get_telegram_notifier()
    return asyncio.run(notifier.send_alert(message, level))