# 🎓 CFAAgent - Asistente Financiero Inteligente

[![LangChain](https://img.shields.io/badge/LangChain-1.0+-blue)](https://www.langchain.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-green)](https://langchain-ai.github.io/langgraph/)
[![Python](https://img.shields.io/badge/Python-3.11+-yellow)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-red)](LICENSE)

**CFAAgent** es un sistema multi-agente avanzado especializado en finanzas, diseñado para asistir en el estudio del programa CFA (Chartered Financial Analyst). Implementa una arquitectura empresarial basada en microservicios con clasificación inteligente y RAG optimizado.

---

## 🌟 Características Principales

### 🤖 Sistema Multi-Agente Especializado
- **8 Agentes Especializados**:
  - 🏦 Agente de Renta Fija (6 herramientas CFA Level I)
  - 💼 Agente de Finanzas Corporativas (5 herramientas)
  - 📈 Agente de Equity (Gordon Growth Model)
  - 📊 Agente de Gestión de Portafolios (7 herramientas)
  - 📉 Agente de Derivados (3 herramientas Black-Scholes)
  - 📚 Agente RAG (búsqueda en microservicio)
  - ℹ️ Agente de Ayuda
  - ✍️ Agente de Síntesis

### 🧠 Arquitectura Moderna Simplificada

#### ✅ Sistema de Clasificación LLM Single-Shot
- **Clasificación en 3 categorías**: TEORICA / PRACTICA / AYUDA
- **Optimización de queries** para búsqueda vectorial
- **Traducción automática** al inglés para queries teóricas
- **~0.5s de latencia** por clasificación

#### ✅ Microservicio RAG Independiente
- **Búsqueda multi-query paralela** con timeout
- **Índice inverso O(1)** para términos técnicos
- **Deduplicación robusta** con SHA256
- **Elasticsearch Cloud** como vector store

#### ✅ Resiliencia Multi-LLM
- Cadena de fallback: **Claude → OpenAI → Gemini**
- Alta disponibilidad (~99.9%)
- Ping tests automáticos
- Degradación gradual

---

## 📊 Arquitectura del Sistema
```mermaid
graph TB
    User[👤 Usuario Streamlit] -->|Query| Supervisor[🧠 Supervisor LLM]
    
    Supervisor -->|Clasificación| Decision{Categoría?}
    
    Decision -->|TEORICA| OptimizeQ[📝 Optimiza Query<br/>Español → Inglés<br/>+ Términos CFA]
    Decision -->|PRACTICA| Router[🔀 Router Especialista]
    Decision -->|AYUDA| Help[ℹ️ Agente Ayuda]
    
    OptimizeQ -->|Query Optimizada| RAG[📚 Agente RAG]
    
    RAG -->|HTTP POST| Microservice[☁️ Microservicio RAG<br/>Google Cloud Run]
    
    Microservice -->|Multi-Query| Parallel{Búsqueda Paralela}
    
    Parallel -->|Variación 1| ES1[(🔍 Elasticsearch<br/>Query Original)]
    Parallel -->|Variación 2| ES2[(🔍 Elasticsearch<br/>Query Enriquecida)]
    Parallel -->|Variación 3| ES3[(🔍 Elasticsearch<br/>Keywords)]
    
    ES1 --> Dedupe[🔗 Deduplicación SHA256]
    ES2 --> Dedupe
    ES3 --> Dedupe
    
    Dedupe -->|Top 4-6 Docs| Format[📄 Formateo]
    Format -->|Contexto| RAG
    
    Router -->|VAN, TIR, etc.| FinCorp[💼 Agente Fin. Corp.]
    Router -->|CAPM, Sharpe| Port[📊 Agente Portafolio]
    Router -->|Bonos, Duration| RF[🏦 Agente Renta Fija]
    Router -->|Options, B-S| Deriv[📉 Agente Derivados]
    Router -->|Gordon Growth| Equity[📈 Agente Equity]
    
    FinCorp -->|22 Tools| Calc[🧮 Herramientas CFA<br/>numpy-financial]
    Port --> Calc
    RF --> Calc
    Deriv --> Calc
    Equity --> Calc
    
    Calc -->|Resultado| Response[✅ Respuesta Usuario]
    RAG -->|Contexto| Response
    Help -->|Guía| Response
    
    Response --> PG[(🗄️ PostgreSQL<br/>Checkpoints)]
    
    style Microservice fill:#e1f5ff
    style ES1 fill:#fff4e1
    style ES2 fill:#fff4e1
    style ES3 fill:#fff4e1
    style PG fill:#e8f5e9
    style Supervisor fill:#f3e5f5
    style Decision fill:#fff9c4
```

### 🔄 Flujo Detallado de Clasificación
```mermaid
sequenceDiagram
    participant U as Usuario
    participant S as Supervisor
    participant LLM as Claude/OpenAI
    participant R as Agente RAG
    participant M as Microservicio RAG
    participant E as Elasticsearch
    participant A as Agente Especialista
    
    U->>S: "¿Qué es el WACC?"
    
    rect rgb(230, 240, 255)
        Note over S,LLM: Clasificación Single-Shot
        S->>LLM: System Prompt + Query
        LLM->>S: {categoria: "TEORICA"<br/>query_optimizada: "WACC definition weighted average cost of capital formula components"<br/>razonamiento: "Pregunta conceptual, material en inglés"}
    end
    
    alt Categoría: TEORICA
        S->>R: Query Optimizada
        R->>M: POST /search
        
        rect rgb(255, 245, 230)
            Note over M,E: Multi-Query Paralelo
            par Variación 1
                M->>E: "WACC definition..."
            and Variación 2
                M->>E: "WACC definition... + sinónimos"
            and Variación 3
                M->>E: "WACC weighted average"
            end
            
            E-->>M: Docs Variación 1
            E-->>M: Docs Variación 2
            E-->>M: Docs Variación 3
            
            M->>M: Deduplicación SHA256
            M->>M: Top 4-6 Docs
        end
        
        M-->>R: Contexto Formateado
        R-->>U: Explicación + Fórmula
        
    else Categoría: PRACTICA
        S->>A: Query Original
        A->>A: Ejecuta Herramienta
        A-->>U: Resultado Numérico
        
    else Categoría: AYUDA
        S->>S: Agente Ayuda
        S-->>U: Guía de Uso
    end
```

---

## 🚀 Inicio Rápido

### Prerrequisitos

- Python 3.11+
- PostgreSQL 15+ (opcional, para persistencia)
- Acceso a Elasticsearch Cloud
- API Keys:
  - Anthropic Claude (primario)
  - OpenAI (fallback + embeddings)
  - Google Gemini (fallback opcional)

### Instalación

1. **Clonar el repositorio**
```bash
git clone https://github.com/Fjgl96/CFAAgent.git
cd CFAAgent
```

2. **Crear entorno virtual**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**
```bash
cp .env.example .env
# Editar .env con tus API keys
```

Variables críticas:
```bash
# API Keys
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-proj-xxx
GOOGLE_API_KEY=AIzaSyxxx  # Opcional

# Microservicio RAG
RAG_API_URL=[https://rag-service-740905672912.us-central1.run.app]

# PostgreSQL (opcional)
ENABLE_POSTGRES_PERSISTENCE=true
POSTGRES_URI=postgresql://user:pass@host:5432/db
```

5. **Ejecutar la aplicación**
```bash
streamlit run streamlit_app.py
```

---

## 💡 Ejemplos de Uso

### 1. Cálculos Financieros (PRACTICA)

**Usuario**: "Calcula VAN: inversión 100k, flujos [30k, 40k, 50k], tasa 10%"

**Sistema**:
```mermaid
graph LR
    A[Supervisor] -->|Clasifica: PRACTICA| B[Agente Fin. Corp]
    B -->|calcular_van| C[numpy-financial]
    C -->|VAN = $2,892.37| D[Usuario]
```

### 2. Búsqueda RAG (TEORICA)

**Usuario**: "¿Qué es el WACC y cómo se calcula?"

**Sistema**:
```mermaid
graph LR
    A[Supervisor] -->|Clasifica: TEORICA| B[Optimiza Query]
    B -->|WACC definition weighted...| C[Microservicio RAG]
    C -->|Multi-Query Paralelo| D[Elasticsearch]
    D -->|Top 4 Docs| E[Síntesis]
    E -->|Definición + Fórmula| F[Usuario]
```

### 3. Ayuda (AYUDA)

**Usuario**: "¿Qué puedes hacer?"

**Sistema**:
```mermaid
graph LR
    A[Supervisor] -->|Clasifica: AYUDA| B[Agente Ayuda]
    B -->|Guía de Uso| C[Usuario]
```

---

## 🛠️ Herramientas Disponibles (22 Total)

### Renta Fija (6)
- `calcular_valor_bono` - Valor presente de bonos
- `calcular_duration_macaulay` - Duration Macaulay
- `calcular_duration_modificada` - Duration Modificada
- `calcular_convexity` - Convexidad
- `calcular_current_yield` - Rendimiento corriente
- `calcular_bono_cupon_cero` - Bonos cupón cero

### Finanzas Corporativas (5)
- `calcular_van` - Valor Actual Neto (NPV)
- `calcular_wacc` - Costo Promedio Ponderado de Capital
- `calcular_tir` - Tasa Interna de Retorno (IRR)
- `calcular_payback_period` - Periodo de Recuperación
- `calcular_profitability_index` - Índice de Rentabilidad

### Equity (1)
- `calcular_gordon_growth` - Modelo Gordon Growth

### Portafolios (7)
- `calcular_capm` - Capital Asset Pricing Model
- `calcular_sharpe_ratio` - Ratio de Sharpe
- `calcular_treynor_ratio` - Ratio de Treynor
- `calcular_jensen_alpha` - Alpha de Jensen
- `calcular_beta_portafolio` - Beta de Portafolio
- `calcular_retorno_portafolio` - Retorno Esperado
- `calcular_std_dev_portafolio` - Desviación Estándar

### Derivados (3)
- `calcular_opcion_call` - Opción Call (Black-Scholes)
- `calcular_opcion_put` - Opción Put (Black-Scholes)
- `calcular_put_call_parity` - Paridad Put-Call

---

## 📁 Estructura del Proyecto
```
CFAAgent/
├── agents/
│   └── financial_agents.py       # Agentes + Clasificador LLM
├── graph/
│   └── agent_graph.py            # Grafo LangGraph + Circuit Breaker
├── tools/
│   ├── financial_tools.py        # 22 herramientas CFA
│   ├── schemas.py                # Pydantic schemas
│   └── help_tools.py             # Ayuda
├── config.py                     # Multi-LLM + PostgreSQL
├── config_elasticsearch.py       # Config Elasticsearch (legacy)
├── streamlit_app.py              # Interfaz Streamlit
├── requirements.txt              # Dependencias
└── README.md                     # Este archivo

Microservicio RAG (Repo Separado):
rag-microservice/
├── main.py                       # FastAPI app
├── rag/
│   └── financial_rag_elasticsearch.py  # Sistema RAG optimizado
├── config.py                     # OpenAI API Key
├── config_elasticsearch.py       # Elasticsearch Cloud
├── requirements.txt
└── Dockerfile                    # Despliegue Google Cloud Run
```

---

## 🔧 Configuración Avanzada

### Microservicio RAG

El sistema RAG corre como microservicio independiente en Google Cloud Run:
```bash
# Desplegar microservicio
cd rag-microservice
gcloud run deploy rag-service \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

Variables de entorno del microservicio:
```bash
OPENAI_API_KEY=sk-xxx
ES_SCHEME=https
ES_HOST=tu-cluster.es.gcp.cloud.es.io
ES_PORT=9200
ES_USERNAME=elastic
ES_PASSWORD=xxx
ES_INDEX_NAME=cfa_documents
EMBEDDING_MODEL=text-embedding-3-large
```

### Habilitar Persistencia PostgreSQL

1. **Crear base de datos**
```sql
CREATE DATABASE cfaagent_db;
```

2. **Configurar .env**
```bash
ENABLE_POSTGRES_PERSISTENCE=true
POSTGRES_URI=postgresql://user:pass@host:5432/cfaagent_db
```

3. **Reiniciar aplicación**
Las tablas se crean automáticamente.

---

## 📈 Comparación de Versiones

| Aspecto | v1.0 (Routing 3 Capas) | v2.0 (Clasificación LLM) |
|---------|------------------------|--------------------------|
| **Routing** | FastPatternRouter + LLMRouter | Clasificación LLM Single-Shot |
| **Latencia** | ~1.3s (con bypass) | ~0.5s (siempre) |
| **Complejidad** | 500+ líneas (3 capas) | ~100 líneas |
| **Mantenibilidad** | Requiere actualizar YAML | Auto-adapta |
| **Casos Ambiguos** | Fallback a LLM | Maneja nativamente |
| **RAG** | Local (volátil) | Microservicio (escalable) |
| **Optimización Query** | No | Sí (traducción + enriquecimiento) |

---

## 🧪 Testing
```bash
# Ejecutar tests
pytest tests/

# Test específico
python tests/test_agents.py
python tests/test_supervisor.py
python tests/test_financial_tools.py

# Validar routing
python test_simple_routing.py
```

---

## 📚 Documentación Adicional

- **[ARQUITECTURA_5_PILARES.md](ARQUITECTURA_5_PILARES.md)** - Guía técnica completa (histórico)
- **[MICROSERVICE_UPDATE_GUIDE.md](MICROSERVICE_UPDATE_GUIDE.md)** - Actualizar microservicio RAG
- **[ARCHITECTURE_IMPLEMENTATION_SUMMARY.md](ARCHITECTURE_IMPLEMENTATION_SUMMARY.md)** - Sistema de routing (deprecado)
- **[LangChain Docs](https://python.langchain.com/)** - Framework principal
- **[LangGraph Docs](https://langchain-ai.github.io/langgraph/)** - Sistema multi-agente

---

## 🤝 Contribuir

1. Fork el proyecto
2. Crear feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit cambios (`git commit -m 'Add AmazingFeature'`)
4. Push al branch (`git push origin feature/AmazingFeature`)
5. Abrir Pull Request

---

## 📝 Changelog

### v2.5.0 (2025-01-29) - Sistema de Clasificación LLM
- ✨ Reemplazo de routing de 3 capas por clasificación LLM simple
- ✨ Optimización automática de queries para RAG (traducción + enriquecimiento)
- ✨ Microservicio RAG independiente en Google Cloud Run
- ✨ Multi-query paralelo con índice inverso O(1)
- 🔧 Eliminación de 500+ líneas de código complejo
- 🔧 Mejor manejo de casos ambiguos

### v2.0.0 (2025-01-22) - Arquitectura de 5 Pilares (Histórico)
- ✨ Ingesta semántica con LlamaIndex
- ✨ Agente ReAct autónomo
- ✨ Persistencia PostgreSQL
- ✨ Multi-LLM resilience (Claude → OpenAI → Gemini)
- 📦 22 herramientas financieras CFA Level I

### v1.0.0 (2024-XX-XX) - MVP Inicial
- Sistema multi-agente básico
- RAG con Elasticsearch
- 15 herramientas financieras
- Interfaz Streamlit

---

## 🐛 Problemas Conocidos

### Microservicio RAG no responde
**Solución**: Verificar que el servicio esté activo
```bash
curl https://rag-service-740905672912.us-central1.run.app/health
```

### PostgreSQL connection refused
**Solución**: Verificar que PostgreSQL esté corriendo
```bash
pg_isready
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.

---

## 👤 Autor

**Felipe Javier García López**
- GitHub: [@Fjgl96](https://github.com/Fjgl96)

---

## 🙏 Agradecimientos

- [LangChain](https://www.langchain.com/) por el framework
- [Anthropic](https://www.anthropic.com/) por Claude
- [Google Cloud](https://cloud.google.com/) por Cloud Run
- CFA Institute por el material de estudio

---

## 📊 Estado del Proyecto

![Status](https://img.shields.io/badge/Status-Active-success)
![Architecture](https://img.shields.io/badge/Architecture-Microservices-blue)
![AI](https://img.shields.io/badge/AI-Multi--Agent-purple)
![Version](https://img.shields.io/badge/Version-2.5.0-blue)

**Última actualización**: 2025-01-29

---

<div align="center">

**⭐ Si este proyecto te resulta útil, considera darle una estrella ⭐**

[![Deployment](https://img.shields.io/badge/Deployed%20on-Google%20Cloud%20Run-blue?logo=google-cloud)](https://cloud.google.com/run)
[![Database](https://img.shields.io/badge/Database-PostgreSQL-336791?logo=postgresql)](https://www.postgresql.org/)
[![Vector Store](https://img.shields.io/badge/Vector%20Store-Elasticsearch-005571?logo=elasticsearch)](https://www.elastic.co/)

</div>
