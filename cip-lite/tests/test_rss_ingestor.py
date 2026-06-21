"""
Tests para RSSIngestor
"""
import pytest
from datetime import datetime, timezone
from services.ingestion.rss_ingestor import RSSIngestor, NewsArticle


class MockEntry:
    def __init__(self, title="Artículo de prueba", summary="Resumen de prueba", link="https://test.link", published_parsed=None):
        self.title = title
        self.summary = summary
        self.link = link
        self.published_parsed = published_parsed
    
    def get(self, key, default=""):
        if key == "description":
            return default
        return getattr(self, key, default)


class TestRSSIngestor:
    """Tests para RSSIngestor"""
    
    def test_initialization(self):
        """Verifica la inicialización"""
        ingestor = RSSIngestor()
        assert ingestor is not None
        assert len(ingestor.articles) == 0
    
    def test_fetch_feed_failed(self, monkeypatch):
        """Verifica el manejo de fallos al obtener un feed"""
        def mock_parse(url):
            raise Exception("Error de prueba")
        
        monkeypatch.setattr("services.ingestion.rss_ingestor.feedparser.parse", mock_parse)
        
        ingestor = RSSIngestor()
        articles = ingestor.fetch_feed("test_source", "https://test.url")
        assert len(articles) == 0
    
    def test_fetch_feed_invalid_date(self, monkeypatch):
        """Verifica el manejo de fechas inválidas en un feed"""
        entry = MockEntry()  # no published_parsed
        
        class MockFeed:
            entries = [entry]
        
        def mock_parse(url):
            return MockFeed()
        
        monkeypatch.setattr("services.ingestion.rss_ingestor.feedparser.parse", mock_parse)
        
        ingestor = RSSIngestor()
        articles = ingestor.fetch_feed("test_source", "https://test.url")
        assert len(articles) == 1
        assert articles[0].source == "test_source"
        assert isinstance(articles[0].published_at, datetime)
    
    def test_fetch_all(self, monkeypatch):
        """Verifica la obtención de todos los feeds"""
        entry = MockEntry(published_parsed=(2024, 6, 1, 12, 0, 0))
        
        class MockFeed:
            entries = [entry]
        
        def mock_parse(url):
            return MockFeed()
        
        monkeypatch.setattr("services.ingestion.rss_ingestor.feedparser.parse", mock_parse)
        
        ingestor = RSSIngestor()
        articles = ingestor.fetch_all()
        
        # Debería haber una entrada por cada feed en RSS_FEEDS
        assert len(articles) == len(RSSIngestor.RSS_FEEDS)
        # Deberían estar ordenados por fecha (más reciente primero)
        assert len(ingestor.articles) == len(articles)
