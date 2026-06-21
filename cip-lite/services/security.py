"""
Módulo de Seguridad Institucional para CIP
- Autenticación JWT
- Rate Limiting
- Cifrado de datos sensibles
- Middleware de seguridad
- Logging de auditoría
"""

import os
import time
import hashlib
import hmac
import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Any
from functools import wraps
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False
    logger.warning("cryptography no instalado. Funcionalidad de cifrado limitada.")


@dataclass
class SecurityConfig:
    """Configuración de seguridad institucional"""
    jwt_secret: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production-123456")
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60
    encryption_key: Optional[bytes] = None

    def __post_init__(self):
        if HAS_CRYPTO and not self.encryption_key:
            env_key = os.getenv("ENCRYPTION_KEY")
            if env_key:
                self.encryption_key = env_key.encode()
            else:
                logger.warning("No ENCRYPTION_KEY found. Generando clave temporal.")
                self.encryption_key = Fernet.generate_key()


class RateLimiter:
    """Rate Limiter institucional basado en memoria"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
        logger.info("Rate Limiter inicializado", max_requests=max_requests, window_seconds=window_seconds)

    def is_allowed(self, client_id: str) -> tuple[bool, Dict[str, Any]]:
        """Verifica si la solicitud está dentro de los límites"""
        now = time.time()
        window_start = now - self.window_seconds

        if client_id not in self.requests:
            self.requests[client_id] = []

        # Filtrar solicitudes antiguas
        self.requests[client_id] = [
            req_time for req_time in self.requests[client_id]
            if req_time > window_start
        ]

        count = len(self.requests[client_id])
        remaining = self.max_requests - count

        if count >= self.max_requests:
            logger.warning("Rate limit excedido", client_id=client_id, count=count)
            return False, {
                "allowed": False,
                "remaining": 0,
                "reset_in": int(self.requests[client_id][0] + self.window_seconds - now)
            }

        self.requests[client_id].append(now)
        return True, {
            "allowed": True,
            "remaining": remaining - 1,
            "reset_in": self.window_seconds
        }


class JWTAuth:
    """Autenticación JWT institucional"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        logger.info("JWT Auth inicializado")

    def _create_signature(self, data: str) -> str:
        """Crea firma HMAC-SHA256"""
        key_bytes = self.config.jwt_secret.encode()
        data_bytes = data.encode()
        signature = hmac.new(key_bytes, data_bytes, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(signature).decode().rstrip('=')

    def generate_token(self, user_id: str, permissions: list[str] = None) -> str:
        """Genera token JWT"""
        payload = {
            "sub": user_id,
            "iat": datetime.now(timezone.utc).timestamp(),
            "exp": (datetime.now(timezone.utc) + timedelta(hours=self.config.jwt_expiration_hours)).timestamp(),
            "permissions": permissions or []
        }

        header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": self.config.jwt_algorithm, "typ": "JWT"}).encode()).decode().rstrip('=')
        payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
        signature = self._create_signature(f"{header_b64}.{payload_b64}")

        token = f"{header_b64}.{payload_b64}.{signature}"
        logger.info("Token JWT generado", user_id=user_id)
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifica y decodifica token JWT"""
        try:
            parts = token.split('.')
            if len(parts) != 3:
                logger.warning("Token JWT inválido: formato incorrecto")
                return None

            header_b64, payload_b64, signature = parts

            # Verificar firma
            expected_signature = self._create_signature(f"{header_b64}.{payload_b64}")
            if not hmac.compare_digest(signature, expected_signature):
                logger.warning("Token JWT inválido: firma incorrecta")
                return None

            # Decodificar payload
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + '=' * (-len(payload_b64) % 4)))

            # Verificar expiración
            if payload["exp"] < datetime.now(timezone.utc).timestamp():
                logger.warning("Token JWT expirado")
                return None

            logger.info("Token JWT verificado", user_id=payload["sub"])
            return payload
        except Exception as e:
            logger.error("Error al verificar token JWT", error=str(e))
            return None


class DataEncryptor:
    """Cifrado de datos sensibles institucional"""

    def __init__(self, config: SecurityConfig):
        self.config = config
        self.fernet: Optional[Fernet] = None
        if HAS_CRYPTO and self.config.encryption_key:
            try:
                self.fernet = Fernet(self.config.encryption_key)
                logger.info("Data Encryptor inicializado")
            except Exception as e:
                logger.error("Error al inicializar Data Encryptor", error=str(e))

    def encrypt(self, data: str) -> str:
        """Cifra datos sensibles"""
        if not self.fernet:
            logger.warning("Cifrado no disponible. Retornando datos sin cifrar.")
            return data
        try:
            encrypted = self.fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            logger.error("Error al cifrar datos", error=str(e))
            return data

    def decrypt(self, encrypted_data: str) -> str:
        """Descifra datos sensibles"""
        if not self.fernet:
            logger.warning("Descifrado no disponible. Retornando datos cifrados.")
            return encrypted_data
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            logger.error("Error al descifrar datos", error=str(e))
            return encrypted_data


class AuditLogger:
    """Logger de auditoría institucional"""

    def __init__(self):
        self.audit_logger = structlog.get_logger("audit")
        logger.info("Audit Logger inicializado")

    def log_access(self, user_id: str, resource: str, action: str, status: str, details: Dict[str, Any] = None):
        """Registra acceso a recursos"""
        self.audit_logger.info(
            "access_log",
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            resource=resource,
            action=action,
            status=status,
            details=details or {}
        )


class SecurityManager:
    """Gestor de seguridad central institucional"""

    def __init__(self):
        self.config = SecurityConfig()
        self.rate_limiter = RateLimiter(
            max_requests=self.config.rate_limit_requests,
            window_seconds=self.config.rate_limit_window_seconds
        )
        self.jwt_auth = JWTAuth(self.config)
        self.encryptor = DataEncryptor(self.config)
        self.audit_logger = AuditLogger()
        logger.info("Security Manager inicializado")

    def require_auth(self, func):
        """Decorador para requerir autenticación"""
        @wraps(func)
        def wrapper(token: str, *args, **kwargs):
            payload = self.jwt_auth.verify_token(token)
            if not payload:
                self.audit_logger.log_access(
                    user_id="unknown",
                    resource=func.__name__,
                    action="access",
                    status="denied"
                )
                raise PermissionError("Autenticación requerida")

            kwargs["user_id"] = payload["sub"]
            kwargs["permissions"] = payload["permissions"]
            return func(*args, **kwargs)
        return wrapper
