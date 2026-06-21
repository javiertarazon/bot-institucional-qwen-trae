"""
Tests para el módulo RSS Ingestor.
"""
import pytest
from datetime import datetime
from services.ingestion.rss_ingestor import RSSIngestor, NewsArticle


class TestRSSIngestor:
    """Suite de tests para RSSIngestor."""
    
    def test_initialization(self):
        """Test que verifica la inicialización correcta del ingestor."""
        ingestor = RSSIngestor()
        assert ingestor is not None
        assert isinstance(ingestor.RSS_FEEDS, dict)
        assert len(ingestor.RSS_FEEDS) > 0
    
    def test_rss_feeds_defined(self):
        """Test que verifica que las fuentes RSS estén definidas."""
        ingestor = RSSIngestor()
        expected_sources = {"coindesk", "cointelegraph", "theblock", "decrypt"}
        assert set(ingestor.RSS_FEEDS.keys()) == expected_sources
    
    def test_news_article_creation(self):
        """Test que verifica la creación de objetos NewsArticle."""
        article = NewsArticle(
            title="Test Article",
            summary="Test summary",
            link="https://example.com",
            published_at=datetime.now(),
            source="test_source"
        )
        assert article.title == "Test Article"
        assert article.summary == "Test summary"
        assert article.link == "https://example.com"
        assert article.source == "test_source"
        assert article.sentiment_score is None
        assert article.entities is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
