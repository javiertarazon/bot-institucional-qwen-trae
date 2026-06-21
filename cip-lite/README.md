# Crypto Intelligence Platform (CIP) Lite v0.3.0

## Descripción
CIP Lite es la versión demo de la plataforma institucional de trading para criptomonedas, utilizando recursos 100% gratuitos.

## Características
- Ingesta de noticias RSS (CoinDesk, Cointelegraph)
- Análisis de sentimiento con DeepSeek
- Validación on-chain con RPC públicos
- Feature Store (Redis + DuckDB)
- Backtesting walk-forward
- Dashboard Streamlit

## Instalación

```bash
# Clonar el repositorio
git init
git add .

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt
```

## Ejecución

```bash
# Iniciar servicios
docker-compose up -d

# Ejecutar dashboard
streamlit run ui/app.py
```

## Estructura del Proyecto
```
cip-lite/
├── services/
│   ├── ingestion/      # Ingesta de datos
│   ├── agents/         # Agentes de IA
│   ├── features/       # Feature Store
│   ├── onchain/        # Validación on-chain
│   └── execution/      # Execution engine
├── ui/                 # Dashboard Streamlit
├── data/               # Datos locales
├── tests/              # Tests
└── docs/               # Documentación
```

## Tecnologías
- Python 3.11+
- FastAPI
- Streamlit
- Redis
- DuckDB
- LangChain
- DeepSeek API
