//! CIP Fast Path - Ultra Low Latency Data Ingestion
//! 
//! Este módulo implementa el Fast Path de CIP en Rust para lograr
//! latencia < 50ms en la ingesta y procesamiento de datos.

use chrono::{DateTime, Utc};
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::io::Cursor;
use thiserror::Error;
use tracing::{debug, error, info, warn};

/// Error personalizado para el Fast Path
#[derive(Error, Debug)]
pub enum FastPathError {
    #[error("HTTP request error: {0}")]
    HttpError(#[from] reqwest::Error),
    
    #[error("RSS parsing error: {0}")]
    RssParseError(String),
    
    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

/// Representa un artículo de noticias
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewsArticle {
    pub title: String,
    pub summary: String,
    pub link: String,
    pub published_at: DateTime<Utc>,
    pub source: String,
}

/// Fuente RSS configurada
#[derive(Debug, Clone)]
pub struct RssSource {
    pub name: String,
    pub url: String,
}

/// Fast Path principal - Ingesta de datos de ultra baja latencia
pub struct FastPath {
    client: Client,
    sources: Vec<RssSource>,
}

impl FastPath {
    /// Crea una nueva instancia del Fast Path
    pub fn new() -> Self {
        let sources = vec![
            RssSource {
                name: "coindesk".to_string(),
                url: "https://www.coindesk.com/arc/outboundfeeds/rss/".to_string(),
            },
            RssSource {
                name: "cointelegraph".to_string(),
                url: "https://cointelegraph.com/rss".to_string(),
            },
            RssSource {
                name: "theblock".to_string(),
                url: "https://www.theblockcrypto.com/rss.xml".to_string(),
            },
            RssSource {
                name: "decrypt".to_string(),
                url: "https://decrypt.co/feed".to_string(),
            },
        ];

        let client = Client::builder()
            .timeout(std::time::Duration::from_secs(10))
            .pool_max_idle_per_host(4)
            .build()
            .expect("Failed to create HTTP client");

        Self { client, sources }
    }

    /// Inicia el proceso de ingesta
    pub async fn run(&self) -> Result<Vec<NewsArticle>, FastPathError> {
        info!("Iniciando Fast Path de CIP");
        
        let mut all_articles = Vec::new();
        
        // Ingestar desde todas las fuentes en paralelo
        let mut handles = Vec::new();
        for source in &self.sources {
            let client = self.client.clone();
            let source = source.clone();
            handles.push(tokio::spawn(async move {
                Self::fetch_source(&client, &source).await
            }));
        }

        // Recopilar resultados
        for handle in handles {
            match handle.await {
                Ok(Ok(articles)) => all_articles.extend(articles),
                Ok(Err(e)) => warn!("Error en fuente: {}", e),
                Err(e) => error!("Error en tarea: {}", e),
            }
        }

        info!("Ingesta completada: {} artículos", all_articles.len());
        
        // Ordenar por fecha (más reciente primero)
        all_articles.sort_by(|a, b| b.published_at.cmp(&a.published_at));
        
        Ok(all_articles)
    }

    /// Obtiene artículos de una fuente RSS específica
    async fn fetch_source(client: &Client, source: &RssSource) -> Result<Vec<NewsArticle>, FastPathError> {
        debug!("Obteniendo artículos de {}", source.name);
        
        let response = client.get(&source.url).send().await?;
        
        if !response.status().is_success() {
            return Err(FastPathError::RssParseError(format!(
                "HTTP Error: {}", response.status()
            )));
        }

        let content = response.text().await?;
        
        // Parsear RSS usando Cursor para BufRead
        let cursor = Cursor::new(content.as_bytes());
        let channel = rss::Channel::read_from(cursor)
            .map_err(|e| FastPathError::RssParseError(e.to_string()))?;

        let mut articles = Vec::new();
        
        for item in channel.items() {
            let title = item.title().unwrap_or_default().to_string();
            let summary = item.description().unwrap_or_default().to_string();
            let link = item.link().unwrap_or_default().to_string();
            
            let published_at = item.pub_date()
                .and_then(|d| DateTime::parse_from_rfc2822(d).ok())
                .map(|d| d.with_timezone(&Utc))
                .unwrap_or_else(Utc::now);

            articles.push(NewsArticle {
                title,
                summary,
                link,
                published_at,
                source: source.name.clone(),
            });
        }

        debug!("Obtenidos {} artículos de {}", articles.len(), source.name);
        Ok(articles)
    }
}

impl Default for FastPath {
    fn default() -> Self {
        Self::new()
    }
}

#[tokio::main]
async fn main() -> Result<(), FastPathError> {
    // Inicializar logging
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .init();

    info!("CIP Fast Path - Versión 0.1.0");
    info!("Iniciando sistema de ingesta de ultra baja latencia");
    
    let fast_path = FastPath::new();
    let articles = fast_path.run().await?;
    
    info!("Resumen de ingesta:");
    info!("  Total de artículos: {}", articles.len());
    
    // Mostrar los 3 primeros artículos
    for (i, article) in articles.iter().take(3).enumerate() {
        info!("\nArtículo {}:", i + 1);
        info!("  Título: {}", article.title);
        info!("  Fuente: {}", article.source);
        info!("  Fecha: {}", article.published_at);
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_fast_path_initialization() {
        let fast_path = FastPath::new();
        assert_eq!(fast_path.sources.len(), 4);
    }

    #[tokio::test]
    async fn test_news_article_creation() {
        let article = NewsArticle {
            title: "Test Article".to_string(),
            summary: "Test Summary".to_string(),
            link: "https://example.com".to_string(),
            published_at: Utc::now(),
            source: "test".to_string(),
        };
        assert_eq!(article.title, "Test Article");
    }
}
