"""
Sistema de Control de Acceso Administrativo
Gestiona permisos, roles y niveles de acceso para Cline
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


class PermissionLevel(Enum):
    """Niveles de acceso al sistema"""
    READ_ONLY = "read_only"
    PAPER_TRADING = "paper_trading"
    LIVE_TRADING = "live_trading"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class Role:
    """Definición de rol con permisos"""
    name: str
    level: PermissionLevel
    permissions: List[str]
    description: str


class AdminAccessControl:
    """
    Sistema de control de acceso para Cline
    Gestiona permisos administrativos y validación de acciones
    """
    
    def __init__(self, cline_bot):
        self.bot = cline_bot
        self.current_role = None
        self.access_log = []
        
        # Definir roles predefinidos
        self.roles = {
            'read_only': Role(
                name='Solo Lectura',
                level=PermissionLevel.READ_ONLY,
                permissions=[
                    'can_analyze_market',
                    'can_view_history',
                    'can_view_metrics'
                ],
                description='Solo análisis, sin ejecución'
            ),
            'paper_trader': Role(
                name='Paper Trader',
                level=PermissionLevel.PAPER_TRADING,
                permissions=[
                    'can_analyze_market',
                    'can_generate_strategies',
                    'can_backtest',
                    'can_open_positions',
                    'can_close_positions',
                    'can_view_history',
                    'can_view_metrics'
                ],
                description='Trading simulado sin dinero real'
            ),
            'live_trader': Role(
                name='Live Trader',
                level=PermissionLevel.LIVE_TRADING,
                permissions=[
                    'can_analyze_market',
                    'can_generate_strategies',
                    'can_backtest',
                    'can_open_positions',
                    'can_close_positions',
                    'can_adjust_stops',
                    'can_access_ccxt',
                    'can_access_mt5',
                    'can_view_history',
                    'can_view_metrics',
                    'can_withdraw_funds'
                ],
                description='Trading real con límites'
            ),
            'admin': Role(
                name='Administrador',
                level=PermissionLevel.ADMIN,
                permissions=[
                    'can_analyze_market',
                    'can_generate_strategies',
                    'can_backtest',
                    'can_open_positions',
                    'can_close_positions',
                    'can_adjust_stops',
                    'can_adjust_risk_params',
                    'can_override_risk_limits',
                    'can_rebalance_portfolio',
                    'can_access_ccxt',
                    'can_access_mt5',
                    'can_download_historical',
                    'can_change_strategy_mode',
                    'emergency_stop',
                    'emergency_liquidation',
                    'can_view_history',
                    'can_view_metrics'
                ],
                description='Acceso total excepto retiros y claves API'
            ),
            'super_admin': Role(
                name='Super Admin',
                level=PermissionLevel.SUPER_ADMIN,
                permissions=[
                    'can_analyze_market',
                    'can_generate_strategies',
                    'can_backtest',
                    'can_open_positions',
                    'can_close_positions',
                    'can_adjust_stops',
                    'can_adjust_risk_params',
                    'can_override_risk_limits',
                    'can_rebalance_portfolio',
                    'can_access_ccxt',
                    'can_access_mt5',
                    'can_download_historical',
                    'can_change_strategy_mode',
                    'emergency_stop',
                    'emergency_liquidation',
                    'can_withdraw_funds',
                    'can_modify_api_keys',
                    'can_view_history',
                    'can_view_metrics',
                    'admin_override'
                ],
                description='Acceso TOTAL - Solo para emergencias'
            )
        }
    
    def grant_role(self, role_name: str) -> Dict[str, any]:
        """
        Otorga un rol predefinido a Cline
        """
        if role_name not in self.roles:
            logger.error(f"Rol desconocido: {role_name}")
            return {"status": "ERROR", "reason": f"Rol '{role_name}' no existe"}
        
        role = self.roles[role_name]
        self.current_role = role
        
        # Aplicar permisos del rol al bot
        self.bot.permissions = {perm: True for perm in role.permissions}
        
        # Establecer modo admin según rol
        self.bot.state.admin_mode = role.level.value in ['admin', 'super_admin', 'live_trading']
        
        logger.info(f"Rol otorgado a Cline: {role.name} ({role.level.value})")
        
        return {
            "status": "SUCCESS",
            "role": role.name,
            "level": role.level.value,
            "permissions_count": len(role.permissions),
            "description": role.description
        }
    
    def grant_admin_permissions(self) -> Dict[str, any]:
        """
        Otorga permisos administrativos completos (ADMIN por defecto)
        """
        result = self.grant_role('admin')
        
        if result['status'] == 'SUCCESS':
            logger.warning("⚠️ Permisos administrativos otorgados a Cline")
            logger.warning(f"   Nivel: {result['level']}")
            logger.warning(f"   Permisos: {result['permissions_count']}")
        
        return result
    
    def grant_super_admin(self) -> Dict[str, any]:
        """
        Otorga permisos de SUPER ADMIN (acceso total)
        """
        result = self.grant_role('super_admin')
        
        if result['status'] == 'SUCCESS':
            logger.warning("🚨 PERMISOS DE SUPER ADMIN OTORGADOS")
            logger.warning("   Cline tiene acceso TOTAL al sistema")
        
        return result
    
    def revoke_permissions(self):
        """Revoca todos los permisos"""
        self.current_role = None
        self.bot.permissions = {}
        self.bot.state.admin_mode = False
        logger.info("Permisos revocados")
    
    def check_permission(self, action: str) -> bool:
        """Verifica si Cline tiene un permiso específico"""
        if not self.current_role:
            return False
        
        return action in self.current_role.permissions
    
    def get_current_role(self) -> Optional[Role]:
        """Obtiene el rol actual"""
        return self.current_role
    
    def list_available_roles(self) -> Dict[str, str]:
        """Lista todos los roles disponibles"""
        return {
            name: role.description 
            for name, role in self.roles.items()
        }
    
    def log_access(self, action: str, status: str, details: Dict = None):
        """Registra una acción en el log de acceso"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'role': self.current_role.name if self.current_role else 'NONE',
            'action': action,
            'status': status,
            'details': details or {}
        }
        self.access_log.append(entry)
        logger.info(f"Access log: {action} → {status}")
    
    def get_access_report(self) -> Dict:
        """Genera reporte de accesos"""
        return {
            'current_role': self.current_role.name if self.current_role else None,
            'total_actions': len(self.access_log),
            'recent_actions': self.access_log[-10:],
            'available_roles': list(self.roles.keys())
        }


# Función de conveniencia
def setup_admin_access(cline_bot, role: str = 'admin') -> AdminAccessControl:
    """
    Configura el control de acceso para Cline
    """
    access_control = AdminAccessControl(cline_bot)
    result = access_control.grant_role(role)
    
    if result['status'] == 'SUCCESS':
        logger.info(f"Sistema de acceso configurado: {result['role']}")
    else:
        logger.error(f"Error configurando acceso: {result['reason']}")
    
    return access_control


if __name__ == "__main__":
    print("=" * 70)
    print("🔐 SISTEMA DE CONTROL DE ACCESO - CLINE")
    print("=" * 70)
    
    # Simular bot (sin dependencias completas)
    class MockBot:
        def __init__(self):
            self.permissions = {}
            self.state = type('obj', (object,), {'admin_mode': False})()
    
    mock_bot = MockBot()
    access_system = AdminAccessControl(mock_bot)
    
    print("\n📋 Roles Disponibles:")
    for role_name, desc in access_system.list_available_roles().items():
        print(f"   • {role_name}: {desc}")
    
    print("\n🔑 Otorgando permisos ADMIN a Cline...")
    result = access_system.grant_admin_permissions()
    
    if result['status'] == 'SUCCESS':
        print(f"✅ Permisos otorgados: {result['role']}")
        print(f"   Nivel: {result['level']}")
        print(f"   Permisos: {result['permissions_count']}")
    
    print("\n🔓 Revocando permisos...")
    access_system.revoke_permissions()
    print("✅ Permisos revocados")
</parameter>
</write_to_file>