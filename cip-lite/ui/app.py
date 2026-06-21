"""
CIP Lite Dashboard - Streamlit UI
Dashboard principal para visualizar noticias, sentimiento y señales.
"""
import streamlit as st
import sys
import os
from datetime import datetime, timedelta

# Añadir el directorio padre al path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.ingestion.rss_ingestor import RSSIngestor

st.set_page_config(
    page_title="CIP Lite - Crypto Intelligence Platform",
    page_icon="🚀",
    layout="wide"
)

# Título principal
st.title("🚀 Crypto Intelligence Platform (CIP) Lite")
st.markdown("---")

# Sidebar
st.sidebar.title("Configuración")
st.sidebar.markdown("### Fuentes de Datos")
sources = st.sidebar.multiselect(
    "Seleccionar fuentes",
    ["coindesk", "cointelegraph", "theblock", "decrypt"],
    default=["coindesk", "cointelegraph"]
)

# Contenedor principal
col1, col2 = st.columns([2, 1])

with col1:
    st.header("📰 Últimas Noticias")
    
    if st.button("Actualizar Noticias", type="primary"):
        with st.spinner("Obteniendo noticias..."):
            ingestor = RSSIngestor()
            articles = ingestor.fetch_all()
            
            if articles:
                st.session_state.articles = articles
                st.success(f"✅ Se obtuvieron {len(articles)} artículos!")
            else:
                st.error("❌ No se pudieron obtener noticias")
    
    # Mostrar artículos
    if "articles" in st.session_state:
        for i, article in enumerate(st.session_state.articles[:10]):
            with st.expander(f"📌 {article.title[:80]}..."):
                st.markdown(f"**Fuente:** {article.source}")
                st.markdown(f"**Fecha:** {article.published_at.strftime('%Y-%m-%d %H:%M')}")
                st.markdown(f"**Resumen:** {article.summary}")
                st.markdown(f"[Leer más]({article.link})")

with col2:
    st.header("📊 Estadísticas")
    
    if "articles" in st.session_state:
        articles = st.session_state.articles
        
        # Estadísticas básicas
        st.metric("Total Artículos", len(articles))
        
        # Contar por fuente
        source_counts = {}
        for a in articles:
            source_counts[a.source] = source_counts.get(a.source, 0) + 1
        
        st.subheader("Por Fuente")
        for source, count in source_counts.items():
            st.write(f"- {source}: {count}")
        
        # Timeline
        st.subheader("Timeline")
        times = [a.published_at for a in articles[:20]]
        st.line_chart(times)

# Footer
st.markdown("---")
st.markdown("*CIP Lite v0.3.0 - Demo con recursos gratuitos*")
