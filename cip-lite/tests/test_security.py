"""
Tests para el módulo de seguridad institucional
"""
import pytest
import time
from datetime import datetime, timedelta
from services.security import (
    SecurityConfig, RateLimiter, JWTAuth, DataEncryptor, AuditLogger, SecurityManager
)


class TestSecurityConfig:
    """Tests para SecurityConfig"""

    def test_initialization_defaults(self):
        """Verifica la inicialización con valores por defecto"""
        config = SecurityConfig()
        assert config.jwt_secret == "dev-secret-change-in-production-123456"
        assert config.jwt_algorithm == "HS256"
        assert config.jwt_expiration_hours == 24
        assert config.rate_limit_requests == 100
        assert config.rate_limit_window_seconds == 60

    def test_post_init_generates_key(self):
        """Verifica que se genera una clave temporal si no hay ENCRYPTION_KEY"""
        config = SecurityConfig()
        assert config.encryption_key is not None


class TestRateLimiter:
    """Tests para RateLimiter"""

    def test_initialization(self):
        """Verifica la inicialización"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 60
        assert len(limiter.requests) == 0

    def test_allows_first_request(self):
        """Verifica que la primera solicitud está permitida"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        allowed, info = limiter.is_allowed("test-client")
        assert allowed is True
        assert info["remaining"] == 9  # 10 - 1 = 9
        assert info["reset_in"] == 60

    def test_blocks_over_limit(self):
        """Verifica que se bloquean solicitudes más allá del límite"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        for _ in range(2):
            allowed, _ = limiter.is_allowed("test-client")
            assert allowed is True
        
        # La tercera debe ser bloqueada
        allowed, info = limiter.is_allowed("test-client")
        assert allowed is False
        assert info["remaining"] == 0

    def test_multiple_clients(self):
        """Verifica que se manejan múltiples clientes independientemente"""
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        
        limiter.is_allowed("client-1")
        limiter.is_allowed("client-1")
        
        # Client 2 debe estar permitido
        allowed, _ = limiter.is_allowed("client-2")
        assert allowed is True


class TestJWTAuth:
    """Tests para JWTAuth"""

    def test_initialization(self):
        """Verifica la inicialización"""
        config = SecurityConfig()
        auth = JWTAuth(config)
        assert auth.config == config

    def test_generate_and_verify_token(self):
        """Verifica que se genera y verifica un token válido"""
        config = SecurityConfig()
        auth = JWTAuth(config)
        token = auth.generate_token("test-user", ["read", "write"])
        
        assert token is not None
        assert len(token.split('.')) == 3
        
        payload = auth.verify_token(token)
        assert payload is not None
        assert payload["sub"] == "test-user"
        assert payload["permissions"] == ["read", "write"]

    def test_verify_invalid_token_format(self):
        """Verifica que tokens con formato incorrecto sean rechazados"""
        config = SecurityConfig()
        auth = JWTAuth(config)
        payload = auth.verify_token("invalid-token-no-dots")
        assert payload is None

    def test_verify_token_with_invalid_signature(self):
        """Verifica que tokens con firma incorrecta sean rechazados"""
        config = SecurityConfig()
        auth = JWTAuth(config)
        token = auth.generate_token("test-user")
        
        # Modificar la firma
        parts = token.split('.')
        invalid_token = f"{parts[0]}.{parts[1]}.invalid-signature"
        
        payload = auth.verify_token(invalid_token)
        assert payload is None


class TestDataEncryptor:
    """Tests para DataEncryptor"""

    def test_initialization(self):
        """Verifica la inicialización"""
        config = SecurityConfig()
        encryptor = DataEncryptor(config)
        assert encryptor.config == config
        assert encryptor.fernet is not None

    def test_encrypt_and_decrypt(self):
        """Verifica el flujo de cifrado y descifrado"""
        config = SecurityConfig()
        encryptor = DataEncryptor(config)
        
        original_data = "mi-api-key-secreta-123"
        
        encrypted = encryptor.encrypt(original_data)
        assert encrypted != original_data
        assert encrypted is not None
        
        decrypted = encryptor.decrypt(encrypted)
        assert decrypted == original_data


class TestAuditLogger:
    """Tests para AuditLogger"""

    def test_initialization(self):
        """Verifica la inicialización"""
        audit = AuditLogger()
        assert audit.audit_logger is not None

    def test_log_access(self):
        """Verifica que se pueda llamar a log_access sin errores"""
        audit = AuditLogger()
        # Solo verificar que no lance excepciones
        audit.log_access(
            user_id="test-user",
            resource="test-resource",
            action="read",
            status="success",
            details={"extra": "info"}
        )


class TestSecurityManager:
    """Tests para SecurityManager"""

    def test_initialization(self):
        """Verifica la inicialización"""
        manager = SecurityManager()
        assert manager.config is not None
        assert manager.rate_limiter is not None
        assert manager.jwt_auth is not None
        assert manager.encryptor is not None
        assert manager.audit_logger is not None

    def test_require_auth_decorator_valid_token(self):
        """Verifica el decorador require_auth con token válido"""
        manager = SecurityManager()
        token = manager.jwt_auth.generate_token("test-user")
        
        @manager.require_auth
        def protected_func(user_id, permissions):
            return {"user_id": user_id, "permissions": permissions}
        
        result = protected_func(token)
        assert result["user_id"] == "test-user"

    def test_require_auth_decorator_invalid_token(self):
        """Verifica el decorador require_auth con token inválido"""
        manager = SecurityManager()
        
        @manager.require_auth
        def protected_func(user_id, permissions):
            return {"user_id": user_id, "permissions": permissions}
        
        with pytest.raises(PermissionError):
            protected_func("invalid-token")
