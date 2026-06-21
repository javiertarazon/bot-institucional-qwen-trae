"""
RSS News Ingestion Module
Ingesta de noticias desde fuentes RSS profesionales.
"""
import feedparser
from datetime import datetime
from typing import List, Dict, Optional
import structlog
from dataclasses import dataclass

logger = structlog.get_logger()


@dataclass
class NewsArticle:
    """Estructura de un artículo de noticias."""
    title: str
    summary: str
    link: str
    published_at: datetime
    source: str
    sentiment_score: Optional[float] = None
    entities: Optional[List[str]] = None


class RSSIngestor:
    """Ingesta de noticias desde RSS feeds."""
    
    # Fuentes RSS profesionales
    RSS_FEEDS = {
        "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
        "cointelegraph": "https://cointelegraph.com/rss",
        "theblock": "https://www.theblockcrypto.com/rss.xml",
        "decrypt": "https://decrypt.co/feed",
    }
    
    def __init__(self):
        self.articles: List[NewsArticle] = []
        logger.info("rss_ingestor_initialized")
    
    def fetch_feed(self, source: str, url: str) -> List[NewsArticle]:
        """Obtiene artículos de un feed RSS."""
        try:
            logger.info("fetching_feed", source=source, url=url)
            feed = feedparser.parse(url)
            articles = []
            
            for entry in feed.entries:
                # Parsear fecha
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    published_at = datetime.utcnow()
                
                article = NewsArticle(
                    title=entry.get("title", ""),
                    summary=entry.get("summary", entry.get("description", "")),
                    link=entry.get("link", ""),
                    published_at=published_at,
                    source=source,
                )
                articles.append(article)
            
            logger.info("feed_fetched", source=source, count=len(articles))
            return articles
            
        except Exception as e:
            logger.error("feed_fetch_failed", source=source, error=str(e))
            return []
    
    def fetch_all(self) -> List[NewsArticle]:
        """Obtiene artículos de todas las fuentes RSS."""
        all_articles = []
        for source, url in self.RSS_FEEDS.items():
            articles = self.fetch_feed(source, url)
            all_articles.extend(articles)
        
        # Ordenar por fecha (más reciente primero)
        all_articles.sort(key=lambda x: x.published_at, reverse=True)
        self.articles = all_articles
        
        logger.info("all_feeds_fetched", total=len(all_articles))
        return all_articles


if __name__ == "__main__":
    # Demo
    ingestor = RSSIngestor()
    articles = ingestor.fetch_all()
    print(f"Fetched {len(articles)} articles")
    for a in articles[:5]:
        print(f"\n[{a.source}] {a.title}")
        print(f"  {a.published_at}")
