#!/usr/bin/env python3
"""Validación Completa de la Fase 2 - CIP"""

import sys
sys.path.insert(0, '.')

print("=" * 70)
print("VALIDACIÓN COMPLETA DE LA FASE 2 - CIP LITE")
print("=" * 70)

tests_passed = 0
tests_total = 0

# Test 1: Ingestion
print("\n[1/6] Probando Ingestión de Noticias...")
try:
    from services.ingestion.rss_ingestor import RSSIngestor
    ingestor = RSSIngestor()
    articles = ingestor.fetch_all()
    print(f"   ✅ OK: {len(articles)} artículos obtenidos")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Test 2: Análisis de Sentimiento
print("\n[2/6] Probando Análisis de Sentimiento...")
try:
    from services.agents.sentiment_analyzer import SentimentAnalyzer
    analyzer = SentimentAnalyzer()
    result, _ = analyzer.analyze("Bitcoin reaches new all-time high")
    print(f"   ✅ OK: Sentimiento = {result.sentiment}")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Test 3: Feature Store
print("\n[3/6] Probando Feature Store...")
try:
    from services.features.store import FeatureStore
    store = FeatureStore()
    print(f"   ✅ OK: Feature Store inicializado")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Test 4: Motor Predictivo
print("\n[4/6] Probando Motor Predictivo ML...")
try:
    from services.ml.predictor import EnsemblePredictor, create_demo_price_data
    predictor = EnsemblePredictor()
    prices = create_demo_price_data(100)
    predictor.train(prices)
    pred = predictor.predict(prices)
    print(f"   ✅ OK: Predicción = {pred['signal']}")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Test 5: Execution Engine
print("\n[5/6] Probando Execution Engine...")
try:
    from services.execution.engine import ExecutionEngine
    engine = ExecutionEngine(100000.0)
    order = engine.create_order("BUY", 0.7, "BTC", 50000.0)
    print(f"   ✅ OK: Orden {order.side if order else 'None'}")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Test 6: Multi-Agent System
print("\n[6/6] Probando Sistema de Agentes...")
try:
    from services.agents.multi_agent_system import create_agent_graph
    app = create_agent_graph()
    print(f"   ✅ OK: Grafo de agentes creado")
    tests_passed += 1
except Exception as e:
    print(f"   ❌ ERROR: {e}")
tests_total += 1

# Resumen
print("\n" + "=" * 70)
print("RESUMEN DE VALIDACIÓN")
print("=" * 70)
print(f"Tests Aprobados: {tests_passed}/{tests_total}")

if tests_passed == tests_total:
    print("\n🎉 TODOS LOS TESTS PASARON! FASE 2 COMPLETA!")
    sys.exit(0)
else:
    print(f"\n⚠️ {tests_total - tests_passed} tests fallaron")
    sys.exit(1)
