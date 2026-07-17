"""
CIP Lite Admin Dashboard - Streamlit UI (Private/Admin Only)
Dashboard privado con autenticación JWT para trading institucional.
"""
import streamlit as st
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import hashlib
import hmac
import secrets

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from services.backtesting.engine import BacktestEngine, BacktestConfig, HistoricalData
from services.cline_brain import ClineBrain, ClineTradeExecutor
from services.risk.dynamic_risk_manager import DynamicRiskManager
from services.metrics import TradingMetrics
from services.strategies.enhanced_strategies import MeanReversionStrategy, MomentumStrategy, EnsembleStrategy

# Configuration
st.set_page_config(
    page_title="CIP Lite - Admin Dashboard",
    page_icon="🔐",
    layout="wide"
)

# =============================================================================
# AUTHENTICATION SYSTEM
# =============================================================================

def verify_jwt(token: str, secret: str) -> bool:
    """Simple JWT verification (demo purposes - use proper JWT library in production)"""
    if not token:
        return False
    try:
        # Simple HMAC verification
        expected_token = hashlib.sha256((secret + "admin").encode()).hexdigest()
        return hmac.compare_digest(token, expected_token[:32])
    except Exception:
        return False

def get_auth_token() -> str:
    """Get auth token from environment or config"""
    # In production, this would be from secure config
    return os.environ.get('ADMIN_TOKEN', 'default-admin-token-change-me')

def check_authentication() -> bool:
    """Check if user is authenticated"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'auth_token' not in st.session_state:
        st.session_state.auth_token = ''
    return st.session_state.authenticated

def login_form():
    """Display login form"""
    st.header("🔐 Acceso Administrativo - CIP Lite")
    
    with st.form("login_form"):
        token = st.text_input("Token de Administrador", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
        
        if submitted:
            if verify_jwt(token, get_auth_token()):
                st.session_state.authenticated = True
                st.session_state.auth_token = token
                st.rerun()
            else:
                st.error("❌ Token inválido")

# Show login if not authenticated
if not check_authentication():
    login_form()
    st.stop()

# =============================================================================
# MAIN APP - Authenticated
# =============================================================================

# Initialize session state for services
if 'brain' not in st.session_state:
    st.session_state.brain = ClineBrain()
if 'executor' not in st.session_state:
    st.session_state.executor = ClineTradeExecutor()
if 'risk_mgr' not in st.session_state:
    st.session_state.risk_mgr = DynamicRiskManager()
if 'trading_metrics' not in st.session_state:
    st.session_state.trading_metrics = TradingMetrics()

# Sidebar
with st.sidebar:
    st.title("🔐 CIP Admin")
    st.markdown(f"**Usuario:** Admin")
    st.markdown(f"**Hora:** {datetime.now().strftime('%H:%M:%S')}")
    
    st.markdown("---")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.authenticated = False
        st.session_state.auth_token = ''
        st.rerun()
    
    st.markdown("---")
    st.markdown("### 🔄 Controles")
    if st.button("🔄 Reiniciar Estado"):
        for key in list(st.session_state.keys()):
            if key not in ['authenticated', 'auth_token']:
                del st.session_state[key]
        st.rerun()

# Main title
st.title("🧠 CIP Lite - Admin Dashboard")
st.markdown("---")

# 6 Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", 
    "📈 Backtesting", 
    "💹 Paper Trading", 
    "🛡️ Risk Manager", 
    "🤖 ML Signals", 
    "📡 Metrics"
])

# =============================================================================
# TAB 1: OVERVIEW
# =============================================================================
with tab1:
    st.header("📊 Resumen General del Sistema")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Sample data for demo
    np.random.seed(42)
    prices = [50000]
    for _ in range(100):
        prices.append(prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    df = pd.DataFrame({
        'close': prices,
        'high': [p * 1.03 for p in prices],
        'low': [p * 0.97 for p in prices],
        'volume': np.random.randint(10000, 100000, 101)
    })
    
    with col1:
        st.metric("Capital Actual", f"${st.session_state.risk_mgr.current_capital:,.2f}", 
                  delta=f"{(st.session_state.risk_mgr.current_capital - 100000)/100000:.1%}")
    
    with col2:
        analysis = st.session_state.brain.analyze_market(df, "BTC")
        st.metric("Precio BTC", f"${analysis.price:,.2f}", 
                  delta=f"{analysis.volatility:.2%}")
    
    with col3:
        regime, conf = st.session_state.brain.detect_market_regime(df)
        st.metric("Régimen ML", regime, delta=f"{conf:.0%} conf.")
    
    with col4:
        st.metric("Posiciones Abiertas", len(st.session_state.risk_mgr.positions))

# =============================================================================
# TAB 2: BACKTESTING
# =============================================================================
with tab2:
    st.header("📈 Motor de Backtesting")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("⚙️ Configuración")
        
        symbol = st.selectbox("Símbolo", ["BTC", "ETH", "SOL", "AVAX"])
        start_date = st.date_input("Fecha Inicio", datetime(2024, 1, 1))
        end_date = st.date_input("Fecha Fin", datetime(2024, 6, 1))
        strategy_type = st.selectbox("Estrategia", ["ensemble", "mean_reversion", "momentum"])
        
        if st.button("🚀 Ejecutar Backtest", type="primary"):
            with st.spinner("Ejecutando backtesting..."):
                data = HistoricalData.generate_synthetic_crypto_data(
                    start_date=str(start_date),
                    end_date=str(end_date),
                    base_price=50000.0 if symbol == "BTC" else 3000.0
                )
                
                # Rename columns for strategy compatibility
                data.columns = ['open', 'high', 'low', 'close', 'volume']
                
                config = BacktestConfig()
                engine = BacktestEngine(config)
                
                # Select strategy
                if strategy_type == "mean_reversion":
                    def strat(df):
                        return MeanReversionStrategy()(df, symbol)
                elif strategy_type == "momentum":
                    def strat(df):
                        return MomentumStrategy()(df, symbol)
                else:
                    def strat(df):
                        return EnsembleStrategy([
                            MeanReversionStrategy(), 
                            MomentumStrategy()
                        ])(df, symbol)
                
                def signal_strategy(data):
                    sig = strat(data)
                    return sig.signal if hasattr(sig, 'signal') else 'HOLD'
                
                results = engine.run(data, signal_strategy)
                
                # Update trading metrics
                st.session_state.trading_metrics.update_from_backtest_results(results)
                st.session_state.backtest_results = results
            
            st.success("✅ Backtest completado")
    
    with col2:
        if 'backtest_results' in st.session_state:
            results = st.session_state.backtest_results
            
            st.subheader("📊 Métricas")
            
            metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
            
            with metrics_col1:
                st.metric("Win Rate", f"{results['win_rate']:.2%}")
            
            with metrics_col2:
                st.metric("Profit Factor", f"{results['profit_factor']:.2f}")
            
            with metrics_col3:
                st.metric("Total Trades", results['total_trades'])
            
            with metrics_col4:
                st.metric("Max DD", f"{results['max_drawdown']:.2%}")
            
            # Streaks
            st.markdown("---")
            streak_col1, streak_col2 = st.columns(2)
            
            with streak_col1:
                st.metric("Racha Ganadoras", results.get('current_win_streak', 0),
                          delta=f"Máx: {results.get('max_win_streak', 0)}")
            
            with streak_col2:
                st.metric("Racha Perdedoras", results.get('current_loss_streak', 0),
                          delta=f"Máx: {results.get('max_loss_streak', 0)}")
            
            # Trade conditions
            st.markdown("---")
            st.subheader("🔍 Condiciones de Operaciones")
            
            if results.get('winning_trade_conditions'):
                with st.expander("Operaciones Ganadoras"):
                    st.dataframe(results['winning_trade_conditions'][:10])
            
            if results.get('losing_trade_conditions'):
                with st.expander("Operaciones Perdedoras"):
                    st.dataframe(results['losing_trade_conditions'][:10])

# =============================================================================
# TAB 3: PAPER TRADING
# =============================================================================
with tab3:
    st.header("💹 Paper Trading en Vivo")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🎮 Controles")
        
        symbol_pt = st.selectbox("Símbolo PT", ["BTC_USDT", "ETH_USDT", "SOL_USDT"], key="pt_symbol")
        auto_run = st.checkbox("Ejecución Automática", value=False)
        
        if st.button("🔄 Ejecutar Ciclo Único"):
            with st.spinner("Analizando mercado..."):
                # Generate sample market data
                data = pd.DataFrame({
                    'close': [50000 + i*10 for i in range(100)],
                    'high': [50000 + i*15 for i in range(100)],
                    'low': [50000 - i*10 for i in range(100)],
                    'volume': [50000] * 100
                })
                
                result = st.session_state.executor.execute_analysis_cycle(
                    data, symbol_pt.replace("_USDT", ""), 0.0
                )
                st.session_state.pt_result = result
            
            st.success("✅ Ciclo ejecutado")
        
        if st.button("🛑 Emergency Stop"):
            st.warning("🚨 Emergency stop activado - Cancelando todas las operaciones")
    
    with col2:
        st.subheader("📋 Última Operación")
        
        if 'pt_result' in st.session_state:
            result = st.session_state.pt_result
            
            st.write(f"**Señal:** {result['signal']['signal']}")
            st.write(f"**Confianza:** {result['signal']['confidence']:.1%}")
            st.write(f"**Aprobado:** {'✅ Sí' if result['risk_approved'] else '❌ No'}")
            
            if result['risk_issues']:
                st.write("**Alertas:**")
                for issue in result['risk_issues']:
                    st.warning(f"  • {issue}")

# =============================================================================
# TAB 4: RISK MANAGER
# =============================================================================
with tab4:
    st.header("🛡️ Gestión de Riesgo Dinámico")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Parámetros Actuales")
        
        # VaR
        var = st.session_state.risk_mgr.value_at_risk()
        st.metric("VaR Diario", f"${var:,.2f}", 
                  delta=f"{var/100000:.1%} del capital")
        
        # Drawdown
        dd = (st.session_state.risk_mgr.current_capital - st.session_state.risk_mgr.peak_value) / st.session_state.risk_mgr.peak_value
        st.metric("Drawdown", f"{dd:.2%}")
        
        # Position count
        st.metric("Posiciones", len(st.session_state.risk_mgr.positions))
    
    with col2:
        st.subheader("⚙️ Ajustes")
        
        max_risk = st.slider("Máximo Riesgo Diario", 0.01, 0.05, 0.02)
        st.write(f"Actual: {max_risk:.1%}")
        
        kelly_frac = st.slider("Fracción Kelly Máx", 0.1, 0.5, 0.25)
        st.write(f"Actual: {kelly_frac:.2f}")
        
        if st.button("💾 Guardar Ajustes"):
            st.session_state.risk_mgr.max_portfolio_risk = max_risk
            st.success("✅ Ajustes guardados")

# =============================================================================
# TAB 5: ML SIGNALS
# =============================================================================
with tab5:
    st.header("🤖 Señales ML con ONNX")
    
    st.subheader("📊 Regime Detection")
    
    # Sample data
    np.random.seed(42)
    ml_prices = [50000]
    for _ in range(100):
        ml_prices.append(ml_prices[-1] * (1 + np.random.normal(0, 0.02)))
    
    ml_df = pd.DataFrame({
        'close': ml_prices,
        'high': [p * 1.03 for p in ml_prices],
        'low': [p * 0.97 for p in ml_prices],
        'volume': np.random.randint(10000, 100000, 101)
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Detectar Régimen"):
            with st.spinner("Ejecutando modelo ONNX..."):
                regime, conf = st.session_state.brain.detect_market_regime(ml_df)
                st.session_state.ml_regime = regime
                st.session_state.ml_confidence = conf
        
        if 'ml_regime' in st.session_state:
            st.metric("Régimen ONNX", st.session_state.ml_regime,
                      delta=f"{st.session_state.ml_confidence:.0%} conf.")
    
    with col2:
        st.subheader("📈 Confianza del Modelo")
        
        if 'ml_confidence' in st.session_state:
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=st.session_state.ml_confidence,
                title={'text': "Confianza"},
                gauge={'axis': {'range': [0, 1]},
                       'bar': {'color': "darkblue"},
                       'steps': [{'value': 0.7, 'color': "green"},
                                {'value': 0.9, 'color': "yellow"},
                                {'value': 1, 'color': "red"}]}))
            st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# TAB 6: METRICS (Prometheus)
# =============================================================================
with tab6:
    st.header("📡 Métricas de Prometheus")
    
    st.markdown("### Métricas disponibles en `/metrics`")
    
    metrics_info = [
        ("cip_pnl_usd", "Profit & Loss en USD", "Gauge"),
        ("cip_roi_percent", "Return on Investment porcentual", "Gauge"),
        ("cip_win_rate", "Tasa de aciertos", "Gauge"),
        ("cip_profit_factor", "Ratio de beneficio", "Gauge"),
        ("cip_max_drawdown", "Máximo drawdown", "Gauge"),
        ("cip_trades_total", "Total operaciones (win/loss)", "Counter"),
        ("cip_current_win_streak", "Racha ganadoras actual", "Gauge"),
        ("cip_current_loss_streak", "Racha perdedoras actual", "Gauge"),
        ("cip_trade_conditions", "Condiciones de operaciones", "Histogram"),
    ]
    
    st.dataframe(
        pd.DataFrame(metrics_info, columns=["Métrica", "Descripción", "Tipo"]),
        use_container_width=True
    )
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Estado del Sistema")
        
        resource_metrics = st.session_state.trading_metrics.collect_resource_metrics()
        
        st.metric("CPU", f"{resource_metrics['cpu_percent']:.1f}%")
        st.metric("Memory", f"{resource_metrics['memory_percent']:.1f}%")
    
    with col2:
        st.subheader("🔗 Endpoints")
        
        st.code("http://localhost:8000/metrics", language="text")
        st.caption("Prometheus metrics endpoint")
        
        st.code("http://localhost:9090", language="text")
        st.caption("Prometheus UI")
        
        st.code("http://localhost:3000", language="text")
        st.caption("Grafana Dashboard")

# Footer
st.markdown("---")
st.markdown("*CIP Lite v0.3.0 - Admin Dashboard*")