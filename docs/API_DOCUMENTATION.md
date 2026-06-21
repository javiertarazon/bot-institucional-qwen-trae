# Documentación de APIs - Modo Lite vs Institucional

## 1. Modo Lite (APIs Gratuitas)

### 1.1 APIs de Datos de Noticias y Sentimiento
| Proveedor | Tipo API | Límite de Uso | Descripción |
|-------------|-----------|----------------|-------------|
| **X (Twitter) API v2 | Free Tier | 500,000 tweets/mes | Datos de tweets para análisis de sentimiento |
| **Reddit API | Free Tier | 60 requests/minuto | Datos de posts/comentarios de Reddit |
| **Google News API | Free Tier | Varía | Fuente de noticias de criptomonedas |

### 1.2 APIs de Datos de Mercado (Free Tier)
| Proveedor | Tipo API | Límite de Uso | Descripción |
|-----------|----------|----------------|-------------|
| **CoinGecko API** | Pública | 50 requests/minuto | Precios, volúmenes, market caps |
| **CoinMarketCap API | Free Tier | 333 requests/día | Datos de mercado de criptos |
| **Blockchair API** | Free Tier | 10 requests/minuto | Datos on-chain (transacciones, bloques) |
| **Etherscan API** | Free Tier | 5 requests/segundo | Datos de la blockchain Ethereum |

### 1.3 Configuración (Modo Lite)
1. Crea una cuenta en cada proveedor
2. Obtén las API keys
3. Crea un archivo `.env` en la carpeta `cip-lite/`
```env
# Modo Lite
X_API_KEY=tu_api_key
REDDIT_CLIENT_ID=tu_client_id
REDDIT_CLIENT_SECRET=tu_client_secret
COINGECKO_API_KEY= (opcional)
```

---

## 2. Modo Institucional (APIs Profesionales)

### 2.1 APIs de Datos de Sentimiento Profesionales
| Proveedor | Coste Estimado | Características |
|-----------|-----------------|-------------------|
| **LunarCrush** | $99 - $499/mes | Datos sociales avanzados, alerts en tiempo real |
| **Santiment** | $199 - $999/mes | Análisis on-chain profesional, métricas de mercado |

### 2.2 APIs de Datos de Mercado en Tiempo Real
| Proveedor | Coste Estimado | Características |
|-----------|-----------------|-------------------|
| **Alchemy** | $49 - $499/mes | Nodos dedicados, WebSocket en tiempo real |
| **QuickNode** | $49 - $999/mes | Infraestructura de nodos enterprise |
| **Chainlink Data Feeds | Precio por uso | Datos de oráculos para DeFi |

### 2.3 APIs de Exchanges (Trading en Vivo
| Exchange | Coste | Límite de Trading |
|----------|-------|---------------------|
| **Binance API** | Gratis | Hasta 1200 requests/segundo |
| **Coinbase Advanced Trade API** | Gratis | Tarifas de trading normales |
| **Kraken API** | Gratis | Límites por nivel de cuenta |

### 2.4 Configuración (Modo Institucional)
1. Contacta con los proveedores enterprise
2. Obtén las credenciales
3. Edita el archivo `.env`
```env
# Modo Institucional
LUNARCRUSH_API_KEY=tu_api_key
SANTIMENT_API_KEY=tu_api_key
ALCHEMY_API_KEY=tu_api_key
QUICKNODE_URL=tu_url
BINANCE_API_KEY=tu_binance_key
BINANCE_API_SECRET=tu_binance_secret
COINBASE_API_KEY=tu_coinbase_key
COINBASE_API_SECRET=tu_coinbase_secret
KRAKEN_API_KEY=tu_kraken_key
KRAKEN_API_SECRET=tu_kraken_secret
```

---

## 3. Seguridad de APIs
- **Nunca compartas tus secretos de API en repositorios públicos
- Usa variables de entorno (`.env` file`)
- Implementa rate limiting para evitar exceder límites
- Usa cifrado para credenciales sensibles (módulo `security.py`)
- Monitorea el uso de APIs para evitar gastos inesperados
