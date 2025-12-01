# config.py
"""
Configuración del sistema API Backend.
Sin dependencias de Streamlit.
"""

import os
from pathlib import Path
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Cargar .env en local (en prod lo maneja la plataforma)
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

# ========================================
# API KEYS & URLS
# ========================================
def get_env_var(name: str, required: bool = True) -> str:
    """Obtiene variables de entorno de forma segura."""
    value = os.getenv(name)
    if not value and required:
        raise ValueError(f"❌ Error Config: Variable {name} no encontrada.")
    return value

ANTHROPIC_API_KEY = get_env_var("ANTHROPIC_API_KEY")
OPENAI_API_KEY = get_env_var("OPENAI_API_KEY")
GOOGLE_API_KEY = get_env_var("GOOGLE_API_KEY", required=False)
LANGSMITH_API_KEY = get_env_var("LANGSMITH_API_KEY", required=False)
CIRCUIT_BREAKER_MAX_RETRIES = 2
CIRCUIT_BREAKER_COOLDOWN = 10
# URL DEL MICROSERVICIO RAG
RAG_API_URL = os.getenv("RAG_API_URL", "https://rag-search-m70x.onrender.com")

# ========================================
# LLM CONFIGURATION (Multi-Provider)
# ========================================
LLM_MODEL_PRIMARY = "claude-3-5-haiku-20241022"
LLM_TEMPERATURE = 0.0
_llm_instance = None

def get_llm():
    global _llm_instance
    if _llm_instance: return _llm_instance

    llm_chain = []
    
    # 1. Claude
    if ANTHROPIC_API_KEY:
        llm_chain.append(ChatAnthropic(
            model=LLM_MODEL_PRIMARY, temperature=LLM_TEMPERATURE, 
            api_key=ANTHROPIC_API_KEY, timeout=30.0, max_retries=2
        ))
    
    # 2. OpenAI
    if OPENAI_API_KEY:
        llm_chain.append(ChatOpenAI(
            model="gpt-4o", temperature=LLM_TEMPERATURE, 
            api_key=OPENAI_API_KEY, timeout=30.0, max_retries=2
        ))
    
    # 3. Gemini
    if GOOGLE_API_KEY:
        llm_chain.append(ChatGoogleGenerativeAI(
            model="gemini-1.5-flash", temperature=LLM_TEMPERATURE,
            google_api_key=GOOGLE_API_KEY, timeout=30.0
        ))

    if not llm_chain:
        raise ValueError("❌ No se encontraron API Keys para ningún LLM.")

    _llm_instance = llm_chain[0].with_fallbacks(llm_chain[1:]) if len(llm_chain) > 1 else llm_chain[0]
    return _llm_instance

# ========================================
# PERSISTENCIA
# ========================================
POSTGRES_URI = os.getenv("POSTGRES_URI")
ENABLE_POSTGRES_PERSISTENCE = os.getenv("ENABLE_POSTGRES_PERSISTENCE", "false").lower() == "true"

def get_postgres_uri() -> str:
    return POSTGRES_URI