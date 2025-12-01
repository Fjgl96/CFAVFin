# config.py
"""
Configuración general del sistema + LangSmith + OpenAI.
Actualizado para LangChain 1.0+
"""

import os
from pathlib import Path
import streamlit as st
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI


try:
    from anthropic import AuthenticationError as AnthropicAuthError
except ImportError:
    # Fallback por si la librería no está
    AnthropicAuthError = type('AnthropicAuthError', (Exception,), {})

try:
    from openai import AuthenticationError as OpenAIAuthError
except ImportError:
    OpenAIAuthError = type('OpenAIAuthError', (Exception,), {})



try:
    from utils.logger import is_streamlit_cloud
except ImportError:
    # Fallback por si la importación falla (ej. si está en otro dir)
    def is_streamlit_cloud():
        """Detecta si la app está corriendo en Streamlit Cloud."""
        import os
        return os.getenv('STREAMLIT_IN_CLOUD') == 'true'

IS_IN_CLOUD = is_streamlit_cloud()
# ========================================
# PATHS DEL PROYECTO (CORREGIDO)
# ========================================

BASE_DIR = Path(__file__).resolve().parent

if IS_IN_CLOUD:
    # En Streamlit Cloud, usa rutas relativas (que son efímeras)
    # Si NO necesitas guardar/leer archivos, puedes omitir esto.
    # Si SÍ necesitas leer archivos (ej. un CSV), inclúyelos en tu repo y usa rutas relativas.
    print("☁️ Entorno: Streamlit Cloud. Usando rutas relativas.")
    SHARED_DIR = BASE_DIR / "shared_data" 
    DOCS_DIR = SHARED_DIR / "docs"
    LOGS_DIR = BASE_DIR / "logs_temp" # El logging a archivo está deshabilitado
else:
    # En Local, usa tu ruta persistente
    print("💻 Entorno: Local. Usando /mnt/user-data/shared.")
    SHARED_DIR = Path("/mnt/user-data/shared")

# --- Solo intenta crear directorios si estás en local ---
if not IS_IN_CLOUD:
    try:
        SHARED_DIR.mkdir(parents=True, exist_ok=True)
        DOCS_DIR = SHARED_DIR / "docs"
        LOGS_DIR = SHARED_DIR / "logs"
        DOCS_DIR.mkdir(exist_ok=True)
        LOGS_DIR.mkdir(exist_ok=True)
        print(f"✅ Directorios locales verificados en {SHARED_DIR}")
    except PermissionError:
        print(f"❌ Permiso denegado para escribir en {SHARED_DIR}. Revisa tus permisos locales.")
        # Fallback a rutas locales relativas si /mnt falla
        SHARED_DIR = BASE_DIR / "shared_data"
        DOCS_DIR = SHARED_DIR / "docs"
        LOGS_DIR = BASE_DIR / "logs_temp"
        
if IS_IN_CLOUD:
    # Asegura que las variables existan
    DOCS_DIR = SHARED_DIR / "docs"
    LOGS_DIR = BASE_DIR / "logs_temp"
    
    # En la nube, SÍ necesitas crear los directorios relativos si vas a usarlos
    # (ej. para subir un archivo y procesarlo)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
# ========================================
# API KEYS
# ========================================

_ANTHROPIC_API_KEY = None
_LANGSMITH_API_KEY = None
_OPENAI_API_KEY = None

def load_api_key(secret_name: str, env_var_name: str, required: bool = True) -> str:
    """Carga una API key desde Streamlit secrets o variables de entorno."""
    loaded_key = None
    source = "unknown"

    try:
        # Intenta Streamlit Secrets primero
        loaded_key = st.secrets[secret_name]
        source = "Streamlit secrets"
        print(f"🔑 Cargada {secret_name} desde {source}.")
        return loaded_key
    except (FileNotFoundError, KeyError, AttributeError):
        # Intenta variables de entorno
        try:
            from dotenv import load_dotenv
            dotenv_path = BASE_DIR / '.env'
            if dotenv_path.exists():
                load_dotenv(dotenv_path=dotenv_path)
                print("📄 Archivo .env cargado.")
            else:
                load_dotenv()
        except ImportError:
            print("⚠️ python-dotenv no instalado.")
        
        loaded_key = os.getenv(env_var_name)
        if loaded_key:
            source = "variables de entorno"
            print(f"🔑 Cargada {env_var_name} desde {source}.")
            return loaded_key
        else:
            if required:
                error_message = f"{env_var_name} no encontrada. Configúrala en secrets o .env"
                st.error(error_message)
                print(f"❌ {error_message}")
                st.stop()
            else:
                print(f"⚠️ {env_var_name} no encontrada (opcional).")
                return None
    except Exception as e:
        st.error(f"Error inesperado al cargar {secret_name}: {e}")
        print(f"❌ Error al cargar {secret_name}: {e}")
        if required:
            st.stop()
        return None

# Cargar API keys
ANTHROPIC_API_KEY = load_api_key("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", required=True)
LANGSMITH_API_KEY = load_api_key("LANGSMITH_API_KEY", "LANGSMITH_API_KEY", required=False)
OPENAI_API_KEY = load_api_key("OPENAI_API_KEY", "OPENAI_API_KEY", required=True)  # ⚡ NUEVO
RAG_API_URL = "https://rag-service-740905672912.us-central1.run.app/" # ⚡ NUEVO
# ========================================
# LANGSMITH CONFIGURATION
# ========================================

# Habilitar LangSmith si hay API key
LANGSMITH_ENABLED = LANGSMITH_API_KEY is not None

if LANGSMITH_ENABLED:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "financial-agent-prod")
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"
    print("✅ LangSmith habilitado")
    print(f"   Proyecto: {os.environ['LANGCHAIN_PROJECT']}")
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    print("⚠️ LangSmith deshabilitado (no hay API key)")

# ========================================
# LLM CONFIGURATION
# ========================================

LLM_MODEL = "claude-3-5-haiku-20241022"  # Modelo actualizado
LLM_TEMPERATURE = 0.1

_llm_instance = None

LLM_MODEL_PRIMARY = "claude-3-5-haiku-20241022" # Modelo actualizado
LLM_MODEL_FALLBACK = "gpt-4o" # Modelo de respaldo
LLM_TEMPERATURE = 0.0 # Tu temperatura original era 0.1, 0.0 es mejor para agentes

_llm_instance = None

# ========================================
# CACHE CONFIGURATION
# ========================================

# Habilitar cache in-memory para reducir latencia
from langchain.globals import set_llm_cache
from langchain.cache import InMemoryCache

# Inicializar cache in-memory
set_llm_cache(InMemoryCache())
print("✅ Cache de LLM habilitado (InMemoryCache)")

# --- FUNCIÓN 'get_llm' MEJORADA - PATRÓN CHAIN OF RESPONSIBILITY ---
def get_llm():
    """
    Crea una instancia singleton de LLM con fallback multi-modelo resiliente.
    Implementa el patrón Chain of Responsibility.

    Orden de prioridad:
    1. Claude (Anthropic) - Primario
    2. OpenAI - Fallback 1
    3. Google Gemini - Fallback 2

    Ventajas:
    - Resiliencia ante caídas de proveedores
    - Validación de API keys con ping test
    - Degradación gradual de capacidades
    - Logging detallado de estado

    Returns:
        Instancia de LLM con fallbacks configurados
    """
    global _llm_instance

    # Si la instancia ya existe, la devuelve
    if _llm_instance is not None:
        return _llm_instance

    # Si no, la crea (Lógica de Fallback Multi-LLM)
    print("🧠 Creando instancia singleton de LLM con fallback resiliente...")

    # Lista de modelos a intentar (Chain of Responsibility)
    llm_chain = []

    # ========================================
    # 1. PRIMARIO: Claude (Anthropic)
    # ========================================
    try:
        if ANTHROPIC_API_KEY:
            llm_claude = ChatAnthropic(
                model=LLM_MODEL_PRIMARY,
                temperature=LLM_TEMPERATURE,
                api_key=ANTHROPIC_API_KEY,
                timeout=30.0,
                max_retries=2
            )
            # Ping test para validar
            llm_claude.invoke("test")
            llm_chain.append(llm_claude)
            print(f"✅ [1/3] Claude {LLM_MODEL_PRIMARY} disponible (Primario)")
        else:
            print("⚠️ [1/3] Claude: API key no configurada")
    except AnthropicAuthError as e:
        print(f"⚠️ [1/3] Claude: Error de autenticación - {e}")
    except Exception as e:
        print(f"⚠️ [1/3] Claude: Error de inicialización - {e}")

    # ========================================
    # 2. FALLBACK 1: OpenAI
    # ========================================
    try:
        if OPENAI_API_KEY:
            llm_openai = ChatOpenAI(
                model=LLM_MODEL_FALLBACK,
                temperature=LLM_TEMPERATURE,
                api_key=OPENAI_API_KEY,
                timeout=30.0,
                max_retries=2
            )
            # Ping test para validar
            llm_openai.invoke("test")
            llm_chain.append(llm_openai)
            print(f"✅ [2/3] OpenAI {LLM_MODEL_FALLBACK} disponible (Fallback 1)")
        else:
            print("⚠️ [2/3] OpenAI: API key no configurada")
    except OpenAIAuthError as e:
        print(f"⚠️ [2/3] OpenAI: Error de autenticación - {e}")
    except Exception as e:
        print(f"⚠️ [2/3] OpenAI: Error de inicialización - {e}")

    # ========================================
    # 3. FALLBACK 2: Google Gemini
    # ========================================
    try:
        google_api_key = load_api_key("GOOGLE_API_KEY", "GOOGLE_API_KEY", required=False)
        if google_api_key:
            from langchain_google_genai import ChatGoogleGenerativeAI

            llm_gemini = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                temperature=LLM_TEMPERATURE,
                google_api_key=google_api_key,
                timeout=30.0,
                max_retries=2
            )
            # Ping test para validar
            llm_gemini.invoke("test")
            llm_chain.append(llm_gemini)
            print("✅ [3/3] Google Gemini disponible (Fallback 2)")
        else:
            print("⚠️ [3/3] Google Gemini: API key no configurada")
    except Exception as e:
        print(f"⚠️ [3/3] Google Gemini: Error de inicialización - {e}")

    # ========================================
    # 4. CONSTRUIR CADENA DE FALLBACKS
    # ========================================
    if len(llm_chain) == 0:
        # ❌ Caso crítico: NINGÚN modelo disponible
        st.error("❌ ERROR CRÍTICO: No se pudo inicializar ningún modelo LLM.")
        st.error("Verifica tus API keys en .env o Streamlit secrets.")
        print("❌ ERROR CRÍTICO: Fallo en la autenticación de TODOS los modelos LLM.")
        st.stop()

    elif len(llm_chain) == 1:
        # ⚠️ Solo UN modelo disponible (sin fallback)
        _llm_instance = llm_chain[0]
        print(f"⚠️ LLM configurado con 1 modelo (SIN fallback)")
        st.warning("⚠️ Sistema funcionando con 1 solo modelo LLM. Considera configurar fallbacks.")

    else:
        # ✅ Múltiples modelos: Construir cadena con with_fallbacks
        _llm_instance = llm_chain[0].with_fallbacks(llm_chain[1:])
        print(f"✅ LLM configurado con {len(llm_chain)} modelos en cadena de fallback")
        print(f"   Orden: {' → '.join([type(llm).__name__ for llm in llm_chain])}")

    return _llm_instance
# ========================================
# OTRAS CONFIGURACIONES
# ========================================

CIRCUIT_BREAKER_MAX_RETRIES = 2
CIRCUIT_BREAKER_COOLDOWN = 10

# ========================================
# POSTGRESQL CONFIGURATION (S26 - Persistencia)
# ========================================

# URI de PostgreSQL para persistencia de checkpoints
# Formato: postgresql://user:password@host:port/database
# Ejemplo local: postgresql://postgres:password@localhost:5432/cfaagent_db
# Ejemplo cloud: postgresql://user:pass@host.provider.com:5432/db_name

POSTGRES_URI = os.getenv(
    "POSTGRES_URI",
    "postgresql://postgres:Claudia_400@34.9.11.83:5432/postgres"
)

# Flag para habilitar/deshabilitar persistencia PostgreSQL
# Si es False, usa MemorySaver (volátil, solo para desarrollo)
ENABLE_POSTGRES_PERSISTENCE = os.getenv("ENABLE_POSTGRES_PERSISTENCE", "false").lower() == "true"

def get_postgres_uri() -> str:
    """
    Retorna la URI de PostgreSQL para persistencia.

    Returns:
        URI de conexión a PostgreSQL
    """
    return POSTGRES_URI
# ========================================
# SISTEMA DE ROLES (OPCIONAL)
# ========================================

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")  # CAMBIAR EN PRODUCCIÓN

def is_admin(password: str) -> bool:
    """Verifica si el password es correcto para admin."""
    return password == ADMIN_PASSWORD

# ========================================
# LOGGING
# ========================================


def check_system_health() -> dict:
    """
    Verifica el estado de todos los componentes del sistema.
    
    Returns:
        Diccionario con estado de cada componente
    """
    health = {
        "anthropic": False,
        "langsmith": False,
        "elasticsearch": False,
        "llm": False
    }
    
    # Check Anthropic API Key
    health["anthropic"] = ANTHROPIC_API_KEY is not None
    
    # Check LangSmith
    health["langsmith"] = LANGSMITH_ENABLED
    
    # Check Elasticsearch
    try:
        es_client = get_elasticsearch_client()
        if es_client and es_client.ping():
            health["elasticsearch"] = True
    except:
        pass
    
    # Check LLM
    try:
        llm = get_llm()
        health["llm"] = llm is not None
    except:
        pass
    
    return health


'''def log_event(event_type: str, data: dict) -> bool:
    """Registra eventos en el log correspondiente."""
    import json
    from datetime import datetime
    
    log_file = LOGS_DIR / f"{event_type}_log.json"
    
    try:
        if log_file.exists():
            with open(log_file, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "data": data
        }
        logs.append(event)
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)
        
        return True
    except Exception as e:
        print(f"❌ Error logging event: {e}")
        return False
'''
print("✅ Módulo config cargado (LangChain 1.0 + LangSmith + OpenAI).")