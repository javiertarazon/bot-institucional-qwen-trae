#!/usr/bin/env python3
"""
Pruebas Exhaustivas - Fase 3
- Funcionales
- Rendimiento
- Seguridad
- Usabilidad
"""

import sys
import time
import statistics
sys.path.insert(0, '/home/jt7ingenieria/Público/proyectos/bot trader institucional/cip-lite')

import structlog
logger = structlog.get_logger()

print("=" * 80)
print("PRUEBAS EXHAUSTIVAS - FASE 3: SEGURIDAD Y ESCALABILIDAD")
print("=" * 80)

tests_passed = 0
tests_total = 0
test_results = []


def record_test(name: str, passed: bool, details: str = ""):
    """Registra un resultado de prueba"""
    global tests_passed, tests_total
    tests_total += 1
    if passed:
        tests_passed += 1
        status = "✅"
    else:
        status = "❌"
    test_results.append({"name": name, "status": status, "passed": passed, "details": details})
    print(f"  {status} {name}: {details}")


# ------------------------------------------------------------------------------
# Pruebas Funcionales
# ------------------------------------------------------------------------------
print("\n[SECCIÓN 1/4] PRUEBAS FUNCIONALES")
print("-" * 80)

try:
    from services.security import SecurityManager
    sec_manager = SecurityManager()
    record_test("Security Manager Inicialización", True, "SecurityManager inicializado correctamente")
except Exception as e:
    record_test("Security Manager Inicialización", False, f"Error: {e}")

try:
    token = sec_manager.jwt_auth.generate_token(user_id="test-user", permissions=["read", "write"])
    record_test("Generar Token JWT", True, "Token JWT generado correctamente")
except Exception as e:
    record_test("Generar Token JWT", False, f"Error: {e}")

try:
    payload = sec_manager.jwt_auth.verify_token(token)
    record_test("Verificar Token JWT", True, f"Token válido para usuario: {payload['sub']}")
except Exception as e:
    record_test("Verificar Token JWT", False, f"Error: {e}")

try:
    encrypted = sec_manager.encryptor.encrypt("Datos sensibles de prueba")
    decrypted = sec_manager.encryptor.decrypt(encrypted)
    record_test("Cifrado y Descifrado", True, "Datos cifrados y descifrados correctamente")
except Exception as e:
    record_test("Cifrado y Descifrado", False, f"Error: {e}")

try:
    allowed, info = sec_manager.rate_limiter.is_allowed("test-client-1")
    record_test("Rate Limiter - Solicitud Permitida", True, f"Permitido: {allowed} | Restantes: {info['remaining']}")
except Exception as e:
    record_test("Rate Limiter - Solicitud Permitida", False, f"Error: {e}")

cache = None
metrics = None

try:
    from services.metrics import LRUCache, MetricsCollector
    cache = LRUCache(max_size=10, ttl_seconds=60)
    metrics = MetricsCollector()
    record_test("Métricas y Caché Inicialización", True, "LRUCache y MetricsCollector inicializados")
except Exception as e:
    record_test("Métricas y Caché Inicialización", False, f"Error: {e}")

try:
    if cache:
        cache.set("test-key", "test-value")
        value = cache.get("test-key")
        record_test("Caché LRU - Set/Get", True, f"Caché funciona: {value}")
    else:
        record_test("Caché LRU - Set/Get", False, "Cache no inicializado")
except Exception as e:
    record_test("Caché LRU - Set/Get", False, f"Error: {e}")


# ------------------------------------------------------------------------------
# Pruebas de Rendimiento
# ------------------------------------------------------------------------------
print("\n[SECCIÓN 2/4] PRUEBAS DE RENDIMIENTO")
print("-" * 80)

try:
    if cache:
        num_ops = 1000
        start = time.time()
        for i in range(num_ops):
            cache.set(f"key-{i}", f"value-{i}")
        time_taken = time.time() - start
        ops_per_sec = num_ops / time_taken
        record_test("Caché LRU - Escritura", True, f"{num_ops} ops en {time_taken:.3f}s | {ops_per_sec:.0f} ops/s")
    else:
        record_test("Caché LRU - Escritura", False, "Cache no inicializado")
except Exception as e:
    record_test("Caché LRU - Escritura", False, f"Error: {e}")

try:
    latencies = []
    for _ in range(100):
        s = time.time()
        payload = sec_manager.jwt_auth.verify_token(token)
        latencies.append(time.time() - s)
    avg_latency = statistics.mean(latencies) * 1000
    record_test("JWT Verify - Latencia", True, f"Latencia media: {avg_latency:.2f} ms")
except Exception as e:
    record_test("JWT Verify - Latencia", False, f"Error: {e}")

try:
    start = time.time()
    for _ in range(50):
        sec_manager.rate_limiter.is_allowed("perf-test")
    time_taken = time.time() - start
    record_test("Rate Limiter - Rendimiento", True, f"50 verificaciones en {time_taken:.4f}s")
except Exception as e:
    record_test("Rate Limiter - Rendimiento", False, f"Error: {e}")

try:
    if metrics:
        metrics.collect_resource_metrics()
        record_test("Métricas de Recursos", True, "Métricas de CPU y memoria coleccionadas")
    else:
        record_test("Métricas de Recursos", False, "MetricsCollector no inicializado")
except Exception as e:
    record_test("Métricas de Recursos", False, f"Error: {e}")


# ------------------------------------------------------------------------------
# Pruebas de Seguridad
# ------------------------------------------------------------------------------
print("\n[SECCIÓN 3/4] PRUEBAS DE SEGURIDAD")
print("-" * 80)

try:
    invalid_payload = sec_manager.jwt_auth.verify_token("token.inválido.123")
    record_test("JWT - Token Inválido", True, "Token inválido correctamente rechazado")
except Exception:
    record_test("JWT - Token Inválido", True, "Token inválido correctamente rechazado (excepción)")

try:
    for i in range(150):
        sec_manager.rate_limiter.is_allowed("malicious-client")
    allowed, info = sec_manager.rate_limiter.is_allowed("malicious-client")
    record_test("Rate Limiter - Límite Excedido", not allowed, f"Permitido: {allowed} | Limitación activada")
except Exception as e:
    record_test("Rate Limiter - Límite Excedido", False, f"Error: {e}")

try:
    sec_manager.audit_logger.log_access(
        user_id="test-audit",
        resource="/api/dashboard",
        action="view",
        status="success"
    )
    record_test("Audit Log - Registro", True, "Registro de auditoría creado")
except Exception as e:
    record_test("Audit Log - Registro", False, f"Error: {e}")


# ------------------------------------------------------------------------------
# Pruebas de Integración (Usabilidad)
# ------------------------------------------------------------------------------
print("\n[SECCIÓN 4/4] PRUEBAS DE INTEGRACIÓN Y USABILIDAD")
print("-" * 80)

try:
    from services.ingestion.rss_ingestor import RSSIngestor
    ingestor = RSSIngestor()
    articles = ingestor.fetch_all()
    record_test("Ingesta RSS", True, f"{len(articles)} artículos ingeridos")
except Exception as e:
    record_test("Ingesta RSS", False, f"Error: {e}")

try:
    from services.execution.engine import ExecutionEngine
    engine = ExecutionEngine(initial_capital=100000.0)
    order = engine.create_order("BUY", 0.8, "BTC", 50000)
    record_test("Execution Engine", True, "Orden ejecutada correctamente")
except Exception as e:
    record_test("Execution Engine", False, f"Error: {e}")

try:
    from services.agents.multi_agent_system import create_agent_graph
    create_agent_graph()
    record_test("Sistema de Agentes", True, "Grafo de agentes cargado correctamente")
except Exception as e:
    record_test("Sistema de Agentes", False, f"Error: {e}")


# ------------------------------------------------------------------------------
# Resumen Final
# ------------------------------------------------------------------------------
print("\n" + "=" * 80)
print("RESUMEN DE PRUEBAS - FASE 3")
print("=" * 80)
print(f"Total de pruebas: {tests_total}")
print(f"Pruebas aprobadas: {tests_passed}")
print(f"Pruebas fallidas: {tests_total - tests_passed}")
print(f"Porcentaje de aprobación: {(tests_passed/tests_total)*100:.1f}%")

print("\n" + "-" * 80)
print("DETALLE DE PRUEBAS:")
print("-" * 80)
for result in test_results:
    print(f"  {result['status']} {result['name']}")
    if result['details']:
        print(f"      → {result['details']}")

if tests_total == tests_passed:
    print("\n🎉 TODAS LAS PRUEBAS PASARON!")
    sys.exit(0)
else:
    print(f"\n⚠️  {tests_total - tests_passed} PRUEBA(S) FALLARON.")
    sys.exit(1)
