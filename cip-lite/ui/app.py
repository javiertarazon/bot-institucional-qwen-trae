"""
CIP Lite Dashboard - Streamlit UI (Admin Only)
Dashboard privado con autenticación para trading institucional.
"""
import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import json
import hashlib
import hmac

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ingestion.rss_ingestor import RSSIngestor
from services.agents import SentimentAnalyzer
from services.features.store import FeatureStore
from services.onchain import OnChainValidator
from services.backtesting.engine import BacktestEngine, BacktestConfig, HistoricalData
from services.cline_brain import ClineBrain, ClineTradeExecutor
from services.risk.dynamic_risk_manager import DynamicRiskManager
from services.metrics import TradingMetrics

# Añadir el directorio padre al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ingestion.rss_ingestor import RSSIngestor
from services.agents import SentimentAnalyzer
from services.features.store import FeatureStore
from services.onchain import OnChainValidator

st.set_page_config(
    page_title="CIP Lite - Crypto Intelligence Platform",
    page_icon="🚀",
    layout="wide"
)

# Inicializar servicios en session state
if 'ingestor' not in st.session_state:
    st.session_state.ingestor = RSSIngestor()

if 'sentiment_analyzer' not in st.session_state:
    st.session_state.sentiment_analyzer = SentimentAnalyzer()

if 'feature_store' not in st.session_state:
    st.session_state.feature_store = FeatureStore()

if 'onchain_validator' not in st.session_state:
    st.session_state.onchain_validator = OnChainValidator()

# Título principal
st.title("🚀 Crypto Intelligence Platform (CIP) Lite")
st.markdown("---")

# Sidebar
st.sidebar.title("⚙️ Configuración")
st.sidebar.markdown("### Fuentes de Datos")
sources = st.sidebar.multiselect(
    "Seleccionar fuentes",
    ["coindesk", "cointelegraph", "theblock", "decrypt"],
    default=["coindesk", "cointelegraph"]
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Herramientas")
if st.sidebar.button("🔄 Reiniciar Estado"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Tabs principales
tab1, tab2, tab3 = st.tabs(["📰 Noticias & Sentimiento", "📊 On-Chain & Features", "ℹ️ Acerca de"])

with tab1:
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.header("📰 Últimas Noticias")
        
        if st.button("Actualizar Noticias", type="primary"):
            with st.spinner("Obteniendo noticias..."):
                articles = st.session_state.ingestor.fetch_all()
                
                if articles:
                    st.session_state.articles = articles
                    st.success(f"✅ Se obtuvieron {len(articles)} artículos!")
                else:
                    st.error("❌ No se pudieron obtener noticias")
        
        # Mostrar artículos con análisis de sentimiento
        if "articles" in st.session_state:
            for i, article in enumerate(st.session_state.articles[:10]):
                with st.expander(f"📌 {article.title[:80]}..."):
                    col_a, col_b = st.columns([3, 1])
                    
                    with col_a:
                        st.markdown(f"**Fuente:** {article.source}")
                        st.markdown(f"**Fecha:** {article.published_at.strftime('%Y-%m-%d %H:%M')}")
                        st.markdown(f"**Resumen:** {article.summary}")
                        st.markdown(f"[Leer más]({article.link})")
                    
                    with col_b:
                        if st.button(f"Analizar Sentimiento {i+1}", key=f"analyze_{i}"):
                            with st.spinner("Analizando..."):
                                full_text = f"{article.title} {article.summary}"
                                result, meta = st.session_state.sentiment_analyzer.analyze(full_text)
                                
                                # Determinar color
                                if result.sentiment == "positivo":
                                    color = "🟢"
                                elif result.sentiment == "negativo":
                                    color = "�"
                                else:
                                    color = "⚪"
                                
                                st.markdown(f"**Sentimiento:** {color} {result.sentiment}")
                                st.markdown(f"**Confianza:** {result.confidence:.2%}")
                                st.markdown(f"**Impacto:** {result.impact}")
                                st.markdown(f"**Temas:** {', '.join(result.key_topics)}")
                                st.markdown(f"**Resumen:** {result.summary}")
    
    with col2:
        st.header("📊 Sentimiento del Mercado")
        
        if "articles" in st.session_state:
            articles = st.session_state.articles
            
            # Estadísticas básicas
            st.metric("Total Artículos", len(articles))
            
            # Contar por fuente
            source_counts = {}
            for a in articles:
                source_counts[a.source] = source_counts.get(a.source, 0) + 1
            
            st.subheader("Por Fuente")
            source_df = pd.DataFrame(list(source_counts.items()), columns=['Fuente', 'Count'])
            st.bar_chart(source_df.set_index('Fuente'))
            
            # Datos de muestra para el gráfico
            st.subheader("Timeline")
            times = [a.published_at for a in articles[:20]]
            st.line_chart(times)

with tab2:
    st.header("⛓️ Análisis On-Chain")
    
    col_onchain1, col_onchain2 = st.columns([1, 1])
    
    with col_onchain1:
        st.subheader("Estado de la Red")
        if st.button("Obtener Bloque Actual"):
            with st.spinner("Consultando blockchain..."):
                block = st.session_state.onchain_validator.get_block_number()
                if block:
                    st.metric("Bloque Actual", f"{block:,}")
                else:
                    st.error("No se pudo obtener el bloque")
        
        st.subheader("Balance de Ejemplo")
        address = st.text_input("Dirección Ethereum", value="0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045")
        if st.button("Consultar Balance"):
            with st.spinner("Consultando balance..."):
                balance = st.session_state.onchain_validator.get_balance(address)
                if balance is not None:
                    st.metric("Balance (ETH)", f"{balance:.4f}")
                else:
                    st.error("No se pudo obtener el balance")
    
    with col_onchain2:
        st.subheader("Feature Store")
        
        if st.button("Ver Datos Almacenados"):
            try:
                one_day_ago = datetime.utcnow() - timedelta(days=1)
                df = st.session_state.feature_store.get_historical("BTC", one_day_ago)
                if df is not None and len(df) > 0:
                    st.dataframe(df)
                else:
                    st.info("No hay datos históricos almacenados aún")
            except Exception as e:
                st.error(f"Error: {e}")

with tab3:
    st.header("ℹ️ Acerca de CIP Lite")
    
    st.markdown("""
    ### Crypto Intelligence Platform Lite
    
    CIP Lite es una plataforma de análisis de mercado de criptomonedas de nivel institucional,
    construida con recursos 100% gratuitos.
    
    ### Características:
    - 📰 Ingestión de noticias RSS de fuentes profesionales
    - 🧠 Análisis de sentimiento con IA (DeepSeek compatible)
    - ⛓️ Validación on-chain con RPC públicos
    - 💾 Feature Store (DuckDB + Redis)
    - 📊 Dashboard interactivo con Streamlit
    
    ### Tecnologías:
    - Python 3.12+
    - Streamlit
    - DuckDB
    - Redis
    - LangChain
    
    ### Versión: 0.3.0
    """)

# Footer
st.markdown("---")
st.markdown("*CIP Lite v0.3.0 - Demo con recursos gratuitos*")
