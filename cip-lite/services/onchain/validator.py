"""
Módulo On-Chain para CIP Lite
Valida datos y eventos contra la blockchain usando RPC públicos gratuitos
"""
from typing import Optional, Dict, List
import requests
import structlog
from datetime import datetime

logger = structlog.get_logger()


class OnChainValidator:
    """Validador de datos on-chain usando RPC públicos"""
    
    # RPC públicos gratuitos
    PUBLIC_RPCS = {
        "ethereum": [
            "https://rpc.ankr.com/eth",
            "https://eth.llamarpc.com",
            "https://1rpc.io/eth"
        ],
        "binance_smart_chain": [
            "https://rpc.ankr.com/bsc",
            "https://bsc-dataseed1.binance.org"
        ],
        "polygon": [
            "https://rpc.ankr.com/polygon"
        ]
    }
    
    def __init__(self):
        self.current_rpc_index = 0
        self.current_chain = "ethereum"
        logger.info("onchain_validator_initialized")
    
    def _make_rpc_request(self, method: str, params: list, chain: str = "ethereum") -> Optional[Dict]:
        """
        Hace una solicitud RPC
        
        Args:
            method: Método RPC
            params: Parámetros
            chain: Cadena
            
        Returns:
            Resultado o None si falla
        """
        rpcs = self.PUBLIC_RPCS.get(chain, [])
        if not rpcs:
            logger.error("no_rpcs_available", chain=chain)
            return None
        
        for i, rpc_url in enumerate(rpcs):
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "method": method,
                    "params": params,
                    "id": 1
                }
                
                response = requests.post(
                    rpc_url,
                    json=payload,
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    logger.warning("rpc_error", chain=chain, error=result["error"])
                    continue
                
                return result["result"]
                
            except Exception as e:
                logger.warning("rpc_request_failed", chain=chain, url=rpc_url, error=str(e))
                continue
        
        return None
    
    def get_block_number(self, chain: str = "ethereum") -> Optional[int]:
        """Obtiene el número de bloque actual"""
        result = self._make_rpc_request("eth_blockNumber", [], chain)
        if result:
            return int(result, 16)
        return None
    
    def get_balance(self, address: str, chain: str = "ethereum") -> Optional[float]:
        """
        Obtiene el balance de una dirección
        
        Args:
            address: Dirección
            chain: Cadena
            
        Returns:
            Balance en ETH/BNB/MATIC o None
        """
        result = self._make_rpc_request("eth_getBalance", [address, "latest"], chain)
        if result:
            wei = int(result, 16)
            return wei / 10**18
        return None
    
    def get_latest_transactions(self, address: str, chain: str = "ethereum", 
                              limit: int = 10) -> List[Dict]:
        """
        Obtiene transacciones recientes de una dirección (usando explorador API)
        
        Nota: Este método usa APIs públicas de exploradores en lugar de RPC directo
        """
        # Para demo, usamos una respuesta simulada
        logger.info("get_latest_transactions_demo", address=address)
        
        # Datos simulados para demostración
        return [
            {
                "hash": f"0x{''.join(['0']*64)}",
                "from": address,
                "to": "0x000000000000000000000000000000000000dEaD",
                "value": 0.01,
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    
    def validate_event_impact(self, event_description: str) -> Dict:
        """
        Valida el impacto de un evento on-chain
        
        Args:
            event_description: Descripción del evento
            
        Returns:
            Dict con validación
        """
        # Análisis simulado para demo
        logger.info("validating_event_impact", event_desc=event_description[:100])
        
        return {
            "is_valid": True,
            "confidence": 0.7,
            "impact_level": "medio",
            "details": "Validación simulada (requiere API key de explorador para datos reales)",
            "timestamp": datetime.utcnow().isoformat()
        }


if __name__ == "__main__":
    # Prueba del módulo
    validator = OnChainValidator()
    
    print("Testing On-Chain Validator...")
    
    # Obtener número de bloque
    block = validator.get_block_number()
    print(f"\nCurrent block: {block}")
    
    # Obtener balance de Vitalik
    vitalik_address = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
    balance = validator.get_balance(vitalik_address)
    print(f"Vitalik's balance: {balance:.4f} ETH" if balance else "Could not get balance")
    
    # Validar evento
    validation = validator.validate_event_impact("Rumored large BTC transfer from exchange")
    print(f"\nEvent validation: {validation}")
