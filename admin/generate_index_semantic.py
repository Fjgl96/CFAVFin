#!/usr/bin/env python3
"""
generate_index_semantic.py
Script de ADMINISTRADOR para indexar libros CFA usando SEMANTIC CHUNKING.
Implementa el Patrón S29: SemanticSplitterNodeParser de LlamaIndex

CORRECCIÓN APICADA: Pre-splitting para evitar errores de context length (8192 tokens).

USO:
1. Coloca tus libros CFA en: ./data/cfa_books/
2. Configura OPENAI_API_KEY en .env
3. Ejecuta: python admin/generate_index_semantic.py
4. Los documentos se indexan en Elasticsearch con índice semántico

SOLO el administrador ejecuta este script.
"""

import sys
from pathlib import Path
from datetime import datetime
import warnings

# Suprimir warnings de LlamaIndex
warnings.filterwarnings('ignore')

# Añadir el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar configuración de Elasticsearch
from config_elasticsearch import (
    get_elasticsearch_client,
    ES_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    ES_URL,
    ES_USERNAME,
    ES_PASSWORD
)

# Importar API key de OpenAI
from config import OPENAI_API_KEY

# ========================================
# CONFIGURACIÓN
# ========================================

# Donde están los libros CFA (relativo al proyecto)
BOOKS_DIR = Path("./data/cfa_books")

# Nombre del índice semántico (diferente al tradicional)
SEMANTIC_INDEX_NAME = ES_INDEX_NAME + "_semantic"

# ========================================
# FUNCIONES
# ========================================

def print_header(text):
    """Imprime un header bonito."""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def check_prerequisites():
    """Verifica que todo esté listo."""
    print_header("Verificando Prerrequisitos")

    # 0. Verificar OpenAI API Key
    if not OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY no encontrada")
        print("   Configúrala en .env o como variable de entorno:")
        print("   OPENAI_API_KEY=sk-...")
        sys.exit(1)
    else:
        print(f"✅ OpenAI API Key configurada")
        print(f"   Modelo: {EMBEDDING_MODEL}")
        print(f"   Dimensiones: {EMBEDDING_DIMENSIONS}")

    # 1. Verificar carpeta de libros
    if not BOOKS_DIR.exists():
        print(f"❌ ERROR: No existe la carpeta: {BOOKS_DIR}")
        print(f"   Créala y coloca tus PDFs ahí:")
        print(f"   mkdir -p {BOOKS_DIR}")
        sys.exit(1)

    # 2. Contar archivos
    pdf_count = len(list(BOOKS_DIR.rglob("*.pdf")))
    txt_count = len(list(BOOKS_DIR.rglob("*.txt")))
    md_count = len(list(BOOKS_DIR.rglob("*.md")))
    total = pdf_count + txt_count + md_count

    print(f"📚 Libros encontrados:")
    print(f"   PDFs: {pdf_count}")
    print(f"   TXTs: {txt_count}")
    print(f"   Markdowns: {md_count}")
    print(f"   TOTAL: {total}")

    if total == 0:
        print(f"\n❌ ERROR: No hay archivos en {BOOKS_DIR}")
        sys.exit(1)

    # 3. Verificar dependencias de LlamaIndex
    try:
        from llama_index.core.node_parser import SemanticSplitterNodeParser
        from llama_index.embeddings.openai import OpenAIEmbedding
        from llama_index.vector_stores.elasticsearch import ElasticsearchStore
        from llama_index.core import StorageContext, VectorStoreIndex, SimpleDirectoryReader
        print("✅ Dependencias de LlamaIndex instaladas")
    except ImportError as e:
        print(f"❌ ERROR: Falta instalar LlamaIndex")
        print(f"   {e}")
        print(f"\n   Ejecuta: pip install -r requirements.txt")
        sys.exit(1)

    # 4. Verificar conexión a Elasticsearch
    client = get_elasticsearch_client()
    if not client:
        print("❌ ERROR: No se pudo conectar a Elasticsearch")
        sys.exit(1)

    print("\n✅ Todos los prerrequisitos cumplidos\n")
    return True


def load_documents_llamaindex():
    """
    Carga documentos usando SimpleDirectoryReader de LlamaIndex.
    Más simple y eficiente que DirectoryLoader de LangChain.
    """
    print_header("Cargando Documentos con LlamaIndex")

    from llama_index.core import SimpleDirectoryReader

    print(f"📂 Directorio: {BOOKS_DIR}")

    try:
        # SimpleDirectoryReader carga automáticamente PDFs, TXTs, MD, etc.
        reader = SimpleDirectoryReader(
            input_dir=str(BOOKS_DIR),
            recursive=True,
            required_exts=[".pdf", ".txt", ".md"]
        )

        documents = reader.load_data()

        print(f"✅ {len(documents)} documentos cargados\n")

        # Añadir metadata adicional
        for doc in documents:
            source = doc.metadata.get('file_name', '')

            # Detectar Level CFA
            if 'Level_I' in source or 'Level_1' in source:
                doc.metadata['cfa_level'] = 'I'
            elif 'Level_II' in source or 'Level_2' in source:
                doc.metadata['cfa_level'] = 'II'
            elif 'Level_III' in source or 'Level_3' in source:
                doc.metadata['cfa_level'] = 'III'

            doc.metadata['indexed_at'] = datetime.now().isoformat()

        return documents

    except Exception as e:
        print(f"❌ ERROR cargando documentos: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def split_documents_semantic(documents):
    """
    Divide documentos usando SEMANTIC CHUNKING (Patrón S29).

    VENTAJAS vs RecursiveCharacterTextSplitter:
    1. Corta solo cuando hay cambio drástico de tema
    2. Preserva fórmulas financieras completas
    3. Usa embeddings para medir distancia semántica
    4. Mejor para material técnico financiero

    Args:
        documents: Lista de documentos de LlamaIndex

    Returns:
        Lista de nodos semánticos
    """
    print_header("Fragmentación Semántica (S29 Pattern)")

    from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
    from llama_index.embeddings.openai import OpenAIEmbedding

    print(f"🧠 Modelo de embeddings: {EMBEDDING_MODEL}")
    print(f"📊 Método: Semantic Chunking (percentil 95)")
    print(f"   - Corta solo en cambios drásticos de tema")
    print(f"   - Preserva contexto financiero completo\n")

    try:
        # 0. PRE-PROCESAMIENTO DE SEGURIDAD
        # Dividir documentos gigantes en bloques manejables (<8192 tokens)
        # Esto evita el error OpenAI BadRequestError (context length exceeded)
        print("🛡️  Ejecutando pre-split de seguridad (max 4000 tokens)...")
        
        pre_splitter = SentenceSplitter(
            chunk_size=4000,
            chunk_overlap=200
        )
        safe_nodes = pre_splitter.get_nodes_from_documents(documents, show_progress=True)
        print(f"✅ Pre-split completado: {len(documents)} docs originales → {len(safe_nodes)} bloques seguros\n")

        # 1. Inicializar modelo de embeddings
        embed_model = OpenAIEmbedding(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # 2. Crear Semantic Splitter
        # buffer_size=1: evalúa cada oración individualmente
        # breakpoint_percentile_threshold=95: corta solo en top 5% de cambios semánticos
        splitter = SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=embed_model
        )

        print("🔍 Ejecutando análisis semántico...")

        # 3. Fragmentar los nodos seguros
        nodes = splitter.get_nodes_from_documents(safe_nodes, show_progress=True)

        print(f"\n✅ {len(nodes)} nodos semánticos creados")
        print(f"   Promedio: {len(nodes) / max(len(documents), 1):.1f} nodos por documento original\n")

        # Estadísticas de tamaño de chunks
        chunk_sizes = [len(node.text) for node in nodes]
        avg_size = sum(chunk_sizes) / len(chunk_sizes) if chunk_sizes else 0
        min_size = min(chunk_sizes) if chunk_sizes else 0
        max_size = max(chunk_sizes) if chunk_sizes else 0

        print(f"📏 Estadísticas de tamaño:")
        print(f"   Promedio: {avg_size:.0f} caracteres")
        print(f"   Mínimo: {min_size} caracteres")
        print(f"   Máximo: {max_size} caracteres\n")

        return nodes

    except Exception as e:
        print(f"❌ ERROR en fragmentación semántica: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def create_or_recreate_index(es_client):
    """Crea o recrea el índice semántico en Elasticsearch."""
    print_header("Configurando Índice en Elasticsearch")

    # Verificar si el índice existe
    if es_client.indices.exists(index=SEMANTIC_INDEX_NAME):
        print(f"⚠️  El índice '{SEMANTIC_INDEX_NAME}' ya existe.")
        response = input("¿Deseas eliminarlo y recrearlo? (s/n): ")

        if response.lower() == 's':
            print(f"🗑️  Eliminando índice '{SEMANTIC_INDEX_NAME}'...")
            es_client.indices.delete(index=SEMANTIC_INDEX_NAME)
            print("✅ Índice eliminado")
        else:
            print("ℹ️  Los documentos se añadirán al índice existente")
            return

    # Crear índice con mapping para vectores densos
    print(f"🔨 Creando índice '{SEMANTIC_INDEX_NAME}'...")

    index_mapping = {
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "embedding": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMENSIONS,
                    "index": True,
                    "similarity": "cosine"
                },
                "metadata": {"type": "object"}
            }
        }
    }

    es_client.indices.create(index=SEMANTIC_INDEX_NAME, body=index_mapping)
    print(f"✅ Índice '{SEMANTIC_INDEX_NAME}' creado\n")


def index_nodes_to_elasticsearch(nodes):
    """
    Indexa nodos semánticos en Elasticsearch usando LlamaIndex con BATCHING MANUAL.
    Corrige el error de Timeout dividiendo el trabajo en lotes pequeños.
    """
    print_header("Indexando Nodos Semánticos en Elasticsearch")

    from llama_index.vector_stores.elasticsearch import ElasticsearchStore
    from llama_index.core import StorageContext, VectorStoreIndex
    from llama_index.embeddings.openai import OpenAIEmbedding

    print(f"🧠 Modelo de embeddings: {EMBEDDING_MODEL}")
    print(f"📦 Total de nodos: {len(nodes)}")
    print(f"🎯 Índice destino: {SEMANTIC_INDEX_NAME}\n")

    try:
        # 1. Inicializar embeddings
        embed_model = OpenAIEmbedding(
            model=EMBEDDING_MODEL,
            api_key=OPENAI_API_KEY
        )

        # 2. Crear ElasticsearchStore con TIMEOUT aumentado
        # Agregamos request_timeout=300 (5 minutos) y retry_on_timeout=True
        vector_store = ElasticsearchStore(
            index_name=SEMANTIC_INDEX_NAME,
            es_url=ES_URL,
            es_user=ES_USERNAME,
            es_password=ES_PASSWORD,
            request_timeout=300,
            retry_on_timeout=True
        )

        # 3. Crear StorageContext
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # 4. Indexación por LOTES (Batching)
        # LlamaIndex no tiene un "batch_size" directo en from_documents que controle la subida,
        # así que lo hacemos manualmente insertando nodos poco a poco.
        
        batch_size = 200  # Tamaño del lote (seguro para evitar timeouts)
        total_nodes = len(nodes)
        total_batches = (total_nodes + batch_size - 1) // batch_size
        
        print(f"📤 Iniciando indexación por lotes (Total: {total_batches} batches)...")
        
        index = None
        
        for i in range(0, total_nodes, batch_size):
            batch_nodes = nodes[i : i + batch_size]
            current_batch = (i // batch_size) + 1
            
            print(f"   Processing batch {current_batch}/{total_batches} ({len(batch_nodes)} nodos)...")
            
            try:
                if index is None:
                    # Primer lote: Crea el índice inicial
                    index = VectorStoreIndex(
                        batch_nodes,
                        storage_context=storage_context,
                        embed_model=embed_model,
                        show_progress=False
                    )
                else:
                    # Lotes siguientes: Inserta en el índice existente
                    index.insert_nodes(batch_nodes)
                
                print(f"   ✅ Batch {current_batch} completado.")
                
            except Exception as e:
                print(f"   ❌ Error crítico en batch {current_batch}: {e}")
                raise e  # Detenemos si hay error para no perder consistencia

        print(f"\n✅ Todos los {total_nodes} nodos indexados exitosamente.\n")
        return True

    except Exception as e:
        print(f"❌ ERROR GENERAL indexando nodos: {e}")
        import traceback
        traceback.print_exc()
        return False
def verify_index():
    """Verifica que el índice semántico se haya creado correctamente."""
    print_header("Verificando Índice")

    es_client = get_elasticsearch_client()

    try:
        # Contar documentos
        count = es_client.count(index=SEMANTIC_INDEX_NAME)
        doc_count = count['count']

        print(f"✅ Índice verificado:")
        print(f"   Nombre: {SEMANTIC_INDEX_NAME}")
        print(f"   Documentos: {doc_count}")

        # Obtener un documento de muestra
        sample = es_client.search(index=SEMANTIC_INDEX_NAME, size=1)
        if sample['hits']['hits']:
            print(f"   Estado: Activo y funcional ✅\n")

        return True

    except Exception as e:
        print(f"❌ Error verificando índice: {e}")
        return False


def main():
    """Función principal."""
    print("\n" + "🚀"*30)
    print("  INDEXADOR SEMÁNTICO - Sistema CFA")
    print("  LlamaIndex + Semantic Chunking (S29)")
    print("🚀"*30)

    print(f"\n📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Libros: {BOOKS_DIR}")
    print(f"📦 Índice ES: {SEMANTIC_INDEX_NAME}")
    print(f"🧠 Embeddings: {EMBEDDING_MODEL} (OpenAI)")
    print(f"🔬 Método: Semantic Chunking (percentil 95)\n")

    # Confirmar
    response = input("¿Deseas continuar? (s/n): ")
    if response.lower() != 's':
        print("❌ Cancelado por el usuario.")
        sys.exit(0)

    try:
        # 1. Verificar prerrequisitos
        check_prerequisites()

        # 2. Obtener cliente ES
        es_client = get_elasticsearch_client()
        if not es_client:
            print("❌ No se pudo conectar a Elasticsearch")
            sys.exit(1)

        # 3. Configurar índice
        create_or_recreate_index(es_client)

        # 4. Cargar documentos
        documents = load_documents_llamaindex()

        if not documents:
            print("❌ ERROR: No se cargaron documentos.")
            sys.exit(1)

        # 5. Fragmentación SEMÁNTICA (El corazón del S29)
        nodes = split_documents_semantic(documents)

        # 6. Indexar en Elasticsearch
        success = index_nodes_to_elasticsearch(nodes)

        if not success:
            print("❌ ERROR: Fallo en la indexación")
            sys.exit(1)

        # 7. Verificar
        verify_index()

        # Resumen final
        print_header("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"📊 Resumen:")
        print(f"   - Documentos procesados: {len(documents)}")
        print(f"   - Nodos semánticos: {len(nodes)}")
        print(f"   - Índice Elasticsearch: {SEMANTIC_INDEX_NAME}")
        print(f"   - Embeddings: OpenAI {EMBEDDING_MODEL}")
        print(f"   - Método: Semantic Chunking (S29)")
        print(f"\n🎯 Los usuarios ya pueden consultar este material con mejor precisión.\n")
        print(f"💡 Ventaja: Fórmulas financieras ahora se preservan completas.\n")

    except KeyboardInterrupt:
        print("\n\n❌ Proceso cancelado por el usuario.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()