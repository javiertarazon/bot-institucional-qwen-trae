"""
Tests para el módulo de Análisis de Sentimiento.
"""
import pytest
from services.agents import SentimentAnalyzer


class TestSentimentAnalyzer:
    """Suite de tests para SentimentAnalyzer."""
    
    def test_initialization(self):
        """Test que verifica la inicialización correcta del analizador."""
        analyzer = SentimentAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "use_dummy")
    
    def test_dummy_analysis_positive(self):
        """Test que verifica el análisis dummy positivo."""
        analyzer = SentimentAnalyzer()
        result, meta = analyzer.analyze(
            "Bitcoin reaches new all-time high with massive institutional adoption!"
        )
        assert result is not None
        assert result.sentiment in ["positivo", "negativo", "neutro"]
        assert 0 <= result.confidence <= 1
        assert hasattr(result, "impact")
        assert hasattr(result, "key_topics")
    
    def test_dummy_analysis_negative(self):
        """Test que verifica el análisis dummy negativo."""
        analyzer = SentimentAnalyzer()
        result, meta = analyzer.analyze(
            "Major exchange hacked, millions in crypto stolen!"
        )
        assert result is not None
    
    def test_dummy_analysis_neutral(self):
        """Test que verifica el análisis dummy neutro."""
        analyzer = SentimentAnalyzer()
        result, meta = analyzer.analyze(
            "Market showing sideways movement with low volatility"
        )
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
