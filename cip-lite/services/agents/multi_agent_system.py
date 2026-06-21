"""
Sistema de Agentes CIP - LangChain/LangGraph
Arquitectura de multi-agentes para análisis de noticias cripto
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
import operator
from datetime import datetime
from services.agents.sentiment_analyzer import SentimentAnalyzer
from services.onchain.validator import OnChainValidator
import structlog

logger = structlog.get_logger()


class AgentState(TypedDict):
    """Estado del sistema de agentes"""
    messages: Annotated[List[BaseMessage], operator.add]
    articles: List[Dict[str, Any]]
    analyzed_articles: List[Dict[str, Any]]
    onchain_validation: Dict[str, Any]
    final_signals: List[Dict[str, Any]]


class MonitorAgent:
    """Agente Monitor: Filtra y deduplica noticias"""
    
    def __init__(self):
        logger.info("Monitor Agent inicializado")
    
    def process(self, state: AgentState) -> AgentState:
        logger.info("Monitor Agent: Filtrando y deduplicando noticias")
        
        articles = state.get("articles", [])
        
        # Eliminar duplicados por título
        seen_titles = set()
        filtered = []
        for article in articles:
            title = article.get("title", "")
            if title not in seen_titles:
                seen_titles.add(title)
                filtered.append(article)
        
        logger.info(f"Monitor Agent: {len(articles)} -> {len(filtered)} noticias")
        
        return {
            **state,
            "messages": [AIMessage(content=f"Filtradas {len(articles) - len(filtered)} noticias duplicadas")],
            "articles": filtered
        }


class EnrichmentAgent:
    """Agente de Enriquecimiento: Análisis de sentimiento y extracción de entidades"""
    
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
        logger.info("Enrichment Agent inicializado")
    
    def process(self, state: AgentState) -> AgentState:
        logger.info("Enrichment Agent: Analizando sentimiento de noticias")
        
        articles = state.get("articles", [])
        analyzed = []
        
        for article in articles:
            try:
                text = f"{article.get('title', '')} {article.get('summary', '')}"
                sentiment, _ = self.analyzer.analyze(text)
                
                analyzed_article = {
                    **article,
                    "sentiment": sentiment.sentiment,
                    "confidence": sentiment.confidence,
                    "impact": sentiment.impact,
                    "key_topics": sentiment.key_topics,
                    "analyzed_at": datetime.utcnow().isoformat()
                }
                analyzed.append(analyzed_article)
            except Exception as e:
                logger.warning(f"Error analizando artículo: {e}")
                analyzed.append(article)
        
        logger.info(f"Enrichment Agent: Analizadas {len(analyzed)} noticias")
        
        return {
            **state,
            "messages": [AIMessage(content=f"Analizadas {len(analyzed)} noticias")],
            "analyzed_articles": analyzed
        }


class OnChainAgent:
    """Agente On-Chain: Valida eventos contra la blockchain"""
    
    def __init__(self):
        self.validator = OnChainValidator()
        logger.info("On-Chain Agent inicializado")
    
    def process(self, state: AgentState) -> AgentState:
        logger.info("On-Chain Agent: Validando eventos")
        
        validation = {
            "performed_at": datetime.utcnow().isoformat(),
            "status": "simulated",
            "details": "Validación simulada (requiere API keys para datos reales)"
        }
        
        return {
            **state,
            "messages": [AIMessage(content="Validación on-chain completada")],
            "onchain_validation": validation
        }


class MLPredictorAgent:
    """Agente Predictor ML: Predice impacto en el mercado"""
    
    def __init__(self):
        logger.info("ML Predictor Agent inicializado")
    
    def process(self, state: AgentState) -> AgentState:
        logger.info("ML Predictor Agent: Generando señales de trading")
        
        analyzed_articles = state.get("analyzed_articles", [])
        signals = []
        
        for article in analyzed_articles:
            sentiment = article.get("sentiment", "neutral")
            
            # Lógica simple de generación de señales (simulada)
            if sentiment == "positivo":
                signal_type = "BUY"
                confidence = article.get("confidence", 0.5)
            elif sentiment == "negativo":
                signal_type = "SELL"
                confidence = article.get("confidence", 0.5)
            else:
                signal_type = "HOLD"
                confidence = 0.5
            
            signals.append({
                "article": article,
                "signal_type": signal_type,
                "confidence": confidence,
                "generated_at": datetime.utcnow().isoformat()
            })
        
        logger.info(f"ML Predictor Agent: Generadas {len(signals)} señales")
        
        return {
            **state,
            "messages": [AIMessage(content=f"Generadas {len(signals)} señales de trading")],
            "final_signals": signals
        }


class RiskAndExecutionAgent:
    """Agente de Riesgo y Ejecución: Valida señales y aplica gestión de riesgo"""
    
    def __init__(self):
        logger.info("Risk & Execution Agent inicializado")
    
    def process(self, state: AgentState) -> AgentState:
        logger.info("Risk & Execution Agent: Aplicando gestión de riesgo")
        
        signals = state.get("final_signals", [])
        
        # Aplicar filtros de riesgo (simulados)
        validated_signals = []
        for signal in signals:
            if signal.get("confidence", 0) > 0.6:
                signal["risk_validated"] = True
                signal["position_size"] = "small"
            else:
                signal["risk_validated"] = False
            
            validated_signals.append(signal)
        
        logger.info(f"Risk & Execution Agent: Validadas {len([s for s in validated_signals if s.get('risk_validated')])} señales")
        
        return {
            **state,
            "messages": [AIMessage(content="Gestión de riesgo aplicada")],
            "final_signals": validated_signals
        }


def create_agent_graph():
    """Crea el grafo de agentes LangGraph"""
    logger.info("Creando grafo de agentes")
    
    # Inicializar agentes
    monitor = MonitorAgent()
    enrichment = EnrichmentAgent()
    onchain = OnChainAgent()
    ml_predictor = MLPredictorAgent()
    risk_exec = RiskAndExecutionAgent()
    
    # Crear el grafo
    graph = StateGraph(AgentState)
    
    # Añadir nodos
    graph.add_node("monitor", monitor.process)
    graph.add_node("enrichment", enrichment.process)
    graph.add_node("onchain", onchain.process)
    graph.add_node("ml_predictor", ml_predictor.process)
    graph.add_node("risk_execution", risk_exec.process)
    
    # Definir flujo
    graph.set_entry_point("monitor")
    graph.add_edge("monitor", "enrichment")
    graph.add_edge("enrichment", "onchain")
    graph.add_edge("onchain", "ml_predictor")
    graph.add_edge("ml_predictor", "risk_execution")
    graph.add_edge("risk_execution", END)
    
    # Compilar
    app = graph.compile()
    
    logger.info("Grafo de agentes creado exitosamente")
    return app


if __name__ == "__main__":
    # Prueba del sistema de agentes
    from services.ingestion.rss_ingestor import RSSIngestor
    
    logger.info("Prueba del sistema de agentes CIP")
    
    # Obtener noticias
    ingestor = RSSIngestor()
    articles_data = ingestor.fetch_all()
    
    # Convertir a dicts
    articles_dicts = []
    for a in articles_data:
        articles_dicts.append({
            "title": a.title,
            "summary": a.summary,
            "link": a.link,
            "published_at": a.published_at.isoformat(),
            "source": a.source
        })
    
    # Crear estado inicial
    initial_state: AgentState = {
        "messages": [HumanMessage(content="Inicio del análisis")],
        "articles": articles_dicts,
        "analyzed_articles": [],
        "onchain_validation": {},
        "final_signals": []
    }
    
    # Crear y ejecutar grafo
    app = create_agent_graph()
    result = app.invoke(initial_state)
    
    logger.info(f"Ejecución completada. Señales generadas: {len(result.get('final_signals', []))}")
