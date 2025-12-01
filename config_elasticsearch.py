# config_elasticsearch.py
"""
Configuración de Elasticsearch para el sistema RAG.
Actualizado para LangChain 1.0+ con OpenAI Embeddings
"""

import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# ========================================
# CREDENCIALES DE ELASTICSEARCH
# ========================================

ES_HOST = os.getenv("ES_HOST", "34.46.107.133")
ES_PORT = int(os.getenv("ES_PORT", "9200"))
ES_USERNAME = os.getenv("ES_USERNAME", "elastic")
ES_PASSWORD = os.getenv("ES_PASSWORD", "+qBe_PiQr*0AT-AAAA")
ES_SCHEME = os.getenv("ES_SCHEME", "https")

# URL completa
ES_URL = f"{ES_SCHEME}://{ES_HOST}:{ES_PORT}"

# ========================================
# CONFIGURACIÓN DEL ÍNDICE
# ========================================

ES_INDEX_NAME = os.getenv("ES_INDEX_NAME", "cfa_documents")

# ========================================
# CONFIGURACIÓN DE EMBEDDINGS - OPENAI
# ========================================

# Modelos disponibles de OpenAI:
# - text-embedding-3-small: 1536 dims, más rápido y económico (RECOMENDADO para producción)
# - text-embedding-3-large: 3072 dims, mejor calidad pero más caro y lento
# - text-embedding-ada-002: 1536 dims, modelo legacy (no recomendado)

# OPTIMIZACIÓN: Usar text-embedding-3-small por defecto para mejor rendimiento/costo
# - 30-50% más rápido que 3-large
# - ~200x más económico ($0.02/M tokens vs $4/M tokens)
# - Calidad suficiente para mayoría de casos de uso
# Si necesitas máxima precisión, cambiar manualmente a text-embedding-3-large
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# Auto-detectar dimensiones según modelo
_model_name = EMBEDDING_MODEL.lower()
if "3-small" in _model_name or "ada-002" in _model_name:
    EMBEDDING_DIMENSIONS = 1536
elif "3-large" in _model_name:
    EMBEDDING_DIMENSIONS = 3072
else:
    EMBEDDING_DIMENSIONS = 1536  # Default seguro

# ========================================
# CONFIGURACIÓN DE CHUNKING
# ========================================

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 250

# ========================================
# FUNCIÓN PARA OBTENER CLIENTE ELASTICSEARCH
# ========================================

def get_elasticsearch_client():
    """Crea y retorna un cliente de Elasticsearch configurado."""
    from elasticsearch import Elasticsearch
    
    try:
        es_client = Elasticsearch(
            [ES_URL],
            basic_auth=(ES_USERNAME, ES_PASSWORD),
            verify_certs=True,  # ⚠️ En producción, usa certificados válidos
            request_timeout=30,
            max_retries=3,
            retry_on_timeout=True
        )
        
        if es_client.ping():
            print(f"✅ Conectado a Elasticsearch en {ES_URL}")
            info = es_client.info()
            print(f"   Cluster: {info['cluster_name']}")
            print(f"   Versión: {info['version']['number']}")
            return es_client
        else:
            print(f"❌ No se pudo conectar a Elasticsearch en {ES_URL}")
            return None
    
    except Exception as e:
        print(f"❌ Error conectando a Elasticsearch: {e}")
        return None

# ========================================
# FUNCIÓN PARA OBTENER CONFIGURACIÓN ES
# ========================================

def get_es_config() -> dict:
    """Retorna configuración para ElasticsearchStore de LangChain."""
    return {
        "es_url": ES_URL,
        "es_user": ES_USERNAME,
        "es_password": ES_PASSWORD,
        "index_name": ES_INDEX_NAME
    }


# ========================================
# VERIFICAR CONEXIÓN AL IMPORTAR
# ========================================

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  TEST DE CONEXIÓN A ELASTICSEARCH")
    print("="*60 + "\n")
    
    client = get_elasticsearch_client()
    
    if client:
        print("\n✅ Conexión exitosa")
        
        try:
            indices = client.cat.indices(format="json")
            print(f"\n📊 Índices existentes ({len(indices)}):")
            for idx in indices[:10]:
                print(f"   - {idx['index']}: {idx['docs.count']} docs")
        except Exception as e:
            print(f"⚠️ No se pudieron listar índices: {e}")
    else:
        print("\n❌ Conexión fallida")
        print("\nVerifica:")
        print(f"  1. Host: {ES_HOST}")
        print(f"  2. Puerto: {ES_PORT}")
        print(f"  3. Usuario: {ES_USERNAME}")
        print(f"  4. Contraseña: {'*' * len(ES_PASSWORD)}")

print("✅ Módulo config_elasticsearch cargado (LangChain 1.0 + OpenAI Embeddings).")