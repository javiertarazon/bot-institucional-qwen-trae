"""
Módulo de Análisis de Sentimiento para CIP Lite
Utiliza LangChain + DeepSeek/Cualquier LLM compatible con OpenAI API
"""
from typing import Optional, Dict, Tuple
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
import structlog

logger = structlog.get_logger()

# Cargar variables de entorno
load_dotenv()


class SentimentAnalysis(BaseModel):
    """Estructura para el análisis de sentimiento"""
    sentiment: str = Field(..., description="Sentimiento: positivo, negativo o neutro")
    confidence: float = Field(..., description="Confianza del análisis (0-1)")
    key_topics: list = Field(..., description="Temas clave mencionados en el texto")
    impact: str = Field(..., description="Impacto potencial en el mercado cripto: alto, medio, bajo o ninguno")
    summary: str = Field(..., description="Resumen breve del análisis")


class SentimentAnalyzer:
    """Analizador de sentimiento para noticias y textos de cripto"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """
        Inicializar el analizador de sentimiento
        
        Args:
            api_key: API key para DeepSeek (si no se proporciona, usa variable de entorno DEEPSEEK_API_KEY)
            model: Nombre del modelo a usar
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        
        if not self.api_key:
            logger.warning("No DEEPSEEK_API_KEY found, using dummy analysis for demonstration")
            self.use_dummy = True
        else:
            self.use_dummy = False
            # Inicializar cliente LLM compatible con OpenAI API (DeepSeek usa la misma interfaz)
            self.llm = ChatOpenAI(
                model=model,
                api_key=self.api_key,
                base_url="https://api.deepseek.com/v1",
                temperature=0.1
            )
            
            # Configurar parser de salida JSON
            self.output_parser = JsonOutputParser(pydantic_object=SentimentAnalysis)
            
            # Crear prompt template
            self.prompt = ChatPromptTemplate.from_messages([
                ("system", """Eres un experto analista de mercado de criptomonedas. Tu trabajo es analizar noticias y textos 
                 sobre cripto y proporcionar un análisis de sentimiento estructurado.
                 
                 Formato de salida JSON:
                 {format_instructions}
                 
                 Considera:
                 - Sentimiento: positivo, negativo o neutro
                 - Confianza: 0-1
                 - Temas clave: criptomonedas específicas, eventos regulatorios, adopción, seguridad, etc.
                 - Impacto en el mercado: alto, medio, bajo o ninguno
                 - Resumen: máximo 2 oraciones
                 """),
                ("user", "Analiza el siguiente texto:\n{text}")
            ])
            
            # Crear chain
            self.chain = self.prompt | self.llm | self.output_parser
        
        logger.info("sentiment_analyzer_initialized", use_dummy=self.use_dummy)
    
    def _dummy_analysis(self, text: str) -> SentimentAnalysis:
        """Análisis de sentimiento simulado para demostración (sin API key)"""
        # Contar palabras clave
        positive_words = ["bullish", "sube", "adopción", "positivo", "éxito", "all-time", "nuevo máximo", "buenas noticias"]
        negative_words = ["bearish", "baja", "hackeo", "scam", "regulación negativa", "caída", "crash", "malas noticias"]
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            sentiment = "positivo"
            confidence = 0.6 + (positive_count * 0.05)
            impact = "medio" if positive_count > 1 else "bajo"
        elif negative_count > positive_count:
            sentiment = "negativo"
            confidence = 0.6 + (negative_count * 0.05)
            impact = "medio" if negative_count > 1 else "bajo"
        else:
            sentiment = "neutro"
            confidence = 0.5
            impact = "ninguno"
        
        return SentimentAnalysis(
            sentiment=sentiment,
            confidence=min(confidence, 0.95),
            key_topics=["criptomonedas", "mercado"],
            impact=impact,
            summary="Análisis simulado sin API key"
        )
    
    def analyze(self, text: str) -> Tuple[SentimentAnalysis, Dict]:
        """
        Analizar el sentimiento de un texto
        
        Args:
            text: Texto a analizar
            
        Returns:
            Tupla con (resultado del análisis, metadata)
        """
        logger.info("analyzing_sentiment", text_length=len(text))
        
        if self.use_dummy:
            result = self._dummy_analysis(text)
        else:
            try:
                result = self.chain.invoke({
                    "text": text,
                    "format_instructions": self.output_parser.get_format_instructions()
                })
            except Exception as e:
                logger.error("sentiment_analysis_failed", error=str(e))
                result = self._dummy_analysis(text)
        
        logger.info("sentiment_analysis_complete", sentiment=result.sentiment)
        return result, {
            "timestamp": os.times()[4],
            "use_dummy": self.use_dummy
        }


if __name__ == "__main__":
    # Prueba del módulo
    analyzer = SentimentAnalyzer()
    
    test_texts = [
        "Bitcoin alcanza nuevo máximo histórico debido a la adopción institucional masiva",
        "Importante hackeo en exchange, pierden $200M en criptomonedas",
        "Mercado lateral sin noticias importantes"
    ]
    
    for text in test_texts:
        result, meta = analyzer.analyze(text)
        print(f"\nTexto: {text}")
        print(f"Sentimiento: {result.sentiment} ({result.confidence:.2f})")
        print(f"Impacto: {result.impact}")
        print(f"Resumen: {result.summary}")
