#!/usr/bin/env python3
"""
generate_index.py
Script de ADMINISTRADOR para indexar libros CFA en Elasticsearch.
Actualizado para LangChain 1.0+ con OpenAI Embeddings

USO:
1. Coloca tus libros CFA en: ./data/cfa_books/
2. Configura OPENAI_API_KEY en .env
3. Ejecuta: python admin/generate_index.py
4. Los documentos se indexan en Elasticsearch

SOLO el administrador ejecuta este script.
"""

import sys
from pathlib import Path
from datetime import datetime

# Añadir el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Importar configuración de Elasticsearch
from config_elasticsearch import (
    get_elasticsearch_client,
    ES_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    CHUNK_SIZE,
    CHUNK_OVERLAP
)

# Importar API key de OpenAI
from config import OPENAI_API_KEY

# ========================================
# CONFIGURACIÓN
# ========================================

# Donde están los libros CFA (relativo al proyecto)
BOOKS_DIR = Path("./data/cfa_books")

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
    
    # 3. Verificar dependencias
    try:
        from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader, TextLoader
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain_openai import OpenAIEmbeddings
        from langchain_elasticsearch import ElasticsearchStore
        from elasticsearch import Elasticsearch
        print("✅ Dependencias instaladas correctamente")
    except ImportError as e:
        print(f"❌ ERROR: Falta instalar dependencias")
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


def load_documents():
    """Carga todos los documentos."""
    print_header("Cargando Documentos")
    
    from langchain_community.document_loaders import (
        DirectoryLoader,
        TextLoader,
        PyPDFLoader,
    )
    
    all_docs = []
    
    # PDFs
    print("📄 Cargando PDFs...")
    try:
        pdf_loader = DirectoryLoader(
            str(BOOKS_DIR),
            glob="**/*.pdf",
            loader_cls=PyPDFLoader,
            show_progress=True
        )
        pdf_docs = pdf_loader.load()
        all_docs.extend(pdf_docs)
        print(f"✅ {len(pdf_docs)} PDFs cargados\n")
    except Exception as e:
        print(f"⚠️  Error cargando PDFs: {e}\n")
    
    # TXTs
    print("📝 Cargando archivos TXT...")
    try:
        txt_loader = DirectoryLoader(
            str(BOOKS_DIR),
            glob="**/*.txt",
            loader_cls=TextLoader,
            show_progress=True
        )
        txt_docs = txt_loader.load()
        all_docs.extend(txt_docs)
        print(f"✅ {len(txt_docs)} TXTs cargados\n")
    except Exception as e:
        print(f"⚠️  Error cargando TXTs: {e}\n")
    
    print(f"📚 TOTAL DOCUMENTOS CARGADOS: {len(all_docs)}\n")
    return all_docs


def split_documents(documents):
    """Divide documentos en chunks."""
    print_header("Dividiendo Documentos en Chunks")
    
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    
    print(f"✂️  Configuración:")
    print(f"   Chunk size: {CHUNK_SIZE}")
    print(f"   Overlap: {CHUNK_OVERLAP}\n")
    
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n## ", "\n\n### ", "\n\n", "\n", ". ", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    
    # Añadir metadata adicional
    for i, chunk in enumerate(chunks):
        source = chunk.metadata.get('source', '')
        
        # Detectar Level CFA
        if 'Level_I' in source or 'Level_1' in source:
            chunk.metadata['cfa_level'] = 'I'
        elif 'Level_II' in source or 'Level_2' in source:
            chunk.metadata['cfa_level'] = 'II'
        elif 'Level_III' in source or 'Level_3' in source:
            chunk.metadata['cfa_level'] = 'III'
        
        chunk.metadata['chunk_id'] = f"chunk_{i+1}"
        chunk.metadata['indexed_at'] = datetime.now().isoformat()
    
    print(f"✅ {len(chunks)} chunks creados")
    print(f"   Promedio: {len(chunks) / max(len(documents), 1):.1f} chunks por documento\n")
    
    return chunks


def create_or_recreate_index(es_client):
    """Crea o recrea el índice en Elasticsearch."""
    print_header("Configurando Índice en Elasticsearch")
    
    # Verificar si el índice existe
    if es_client.indices.exists(index=ES_INDEX_NAME):
        print(f"⚠️  El índice '{ES_INDEX_NAME}' ya existe.")
        response = input("¿Deseas eliminarlo y recrearlo? (s/n): ")
        
        if response.lower() == 's':
            print(f"🗑️  Eliminando índice '{ES_INDEX_NAME}'...")
            es_client.indices.delete(index=ES_INDEX_NAME)
            print("✅ Índice eliminado")
        else:
            print("ℹ️  Los documentos se añadirán al índice existente")
            return
    
    # Crear índice con mapping para vectores densos
    print(f"🔨 Creando índice '{ES_INDEX_NAME}'...")
    
    index_mapping = {
        "mappings": {
            "properties": {
                "text": {"type": "text"},
                "vector": {
                    "type": "dense_vector",
                    "dims": EMBEDDING_DIMENSIONS,  # 1536 para OpenAI text-embedding-3-small
                    "index": True,
                    "similarity": "cosine"
                },
                "metadata": {"type": "object"}
            }
        }
    }
    
    es_client.indices.create(index=ES_INDEX_NAME, body=index_mapping)
    print(f"✅ Índice '{ES_INDEX_NAME}' creado\n")


def estimate_tokens(text: str) -> int:
    """
    Estima la cantidad de tokens en un texto.
    Aproximación: ~4 caracteres = 1 token para inglés.
    """
    return len(text) // 4


def create_batches(chunks, max_tokens_per_batch=250000):
    """
    Divide chunks en batches que no excedan el límite de tokens.

    Args:
        chunks: Lista de documentos
        max_tokens_per_batch: Límite de tokens por batch (dejamos margen de 250k vs 300k límite)

    Returns:
        Lista de lotes de chunks
    """
    batches = []
    current_batch = []
    current_tokens = 0

    for chunk in chunks:
        # Estimar tokens del chunk
        chunk_tokens = estimate_tokens(chunk.page_content)

        # Si añadir este chunk excede el límite, crear nuevo batch
        if current_tokens + chunk_tokens > max_tokens_per_batch and current_batch:
            batches.append(current_batch)
            current_batch = [chunk]
            current_tokens = chunk_tokens
        else:
            current_batch.append(chunk)
            current_tokens += chunk_tokens

    # Añadir último batch si tiene contenido
    if current_batch:
        batches.append(current_batch)

    return batches


def index_documents_to_elasticsearch(chunks):
    """Indexa los chunks en Elasticsearch usando OpenAI Embeddings con batching."""
    print_header("Indexando Documentos en Elasticsearch")

    from langchain_openai import OpenAIEmbeddings
    from langchain_elasticsearch import ElasticsearchStore
    from config_elasticsearch import get_es_config

    print(f"🧠 Modelo de embeddings OpenAI: {EMBEDDING_MODEL}")
    print(f"   Dimensiones: {EMBEDDING_DIMENSIONS}")
    print(f"   ⚡ Velocidad: ~1 segundo por lote\n")

    # Verificar API key
    if not OPENAI_API_KEY:
        print("❌ ERROR: OPENAI_API_KEY no encontrada")
        sys.exit(1)

    # Inicializar embeddings de OpenAI
    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_MODEL,
        openai_api_key=OPENAI_API_KEY,
        chunk_size=500,  # Reducido de 1000 a 500 por seguridad
        max_retries=3
    )

    # Obtener configuración
    es_config = get_es_config()

    # Crear batches para evitar exceder límite de tokens
    print(f"📦 Creando batches de documentos...")
    batches = create_batches(chunks, max_tokens_per_batch=250000)
    print(f"   Total chunks: {len(chunks)}")
    print(f"   Total batches: {len(batches)}")
    print(f"   Chunks por batch (aprox): {len(chunks) // len(batches) if batches else 0}\n")

    try:
        vector_store = None
        total_indexed = 0

        for i, batch in enumerate(batches, 1):
            print(f"📤 Procesando batch {i}/{len(batches)} ({len(batch)} chunks)...")

            if i == 1:
                # Primer batch: crear el vector store
                vector_store = ElasticsearchStore.from_documents(
                    documents=batch,
                    embedding=embeddings,
                    index_name=ES_INDEX_NAME,
                    es_url=es_config["es_url"],
                    es_user=es_config["es_user"],
                    es_password=es_config["es_password"],
                    bulk_kwargs={"request_timeout": 120}
                )
            else:
                # Batches siguientes: añadir al vector store existente
                vector_store.add_documents(
                    documents=batch,
                    bulk_kwargs={"request_timeout": 120}
                )

            total_indexed += len(batch)
            print(f"   ✅ Batch {i} completado ({total_indexed}/{len(chunks)} chunks indexados)")

        print(f"\n✅ Todos los documentos indexados exitosamente ({total_indexed} chunks)\n")
        return True

    except Exception as e:
        print(f"❌ ERROR indexando documentos: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_index():
    """Verifica que el índice se haya creado correctamente."""
    print_header("Verificando Índice")
    
    es_client = get_elasticsearch_client()
    
    try:
        # Contar documentos
        count = es_client.count(index=ES_INDEX_NAME)
        doc_count = count['count']
        
        print(f"✅ Índice verificado:")
        print(f"   Nombre: {ES_INDEX_NAME}")
        print(f"   Documentos: {doc_count}")
        
        # Obtener un documento de muestra
        sample = es_client.search(index=ES_INDEX_NAME, size=1)
        if sample['hits']['hits']:
            print(f"   Estado: Activo y funcional ✅\n")
        
        return True
    
    except Exception as e:
        print(f"❌ Error verificando índice: {e}")
        return False


def main():
    """Función principal."""
    print("\n" + "🚀"*30)
    print("  INDEXADOR ELASTICSEARCH - Sistema CFA")
    print("  LangChain 1.0 + OpenAI Embeddings")
    print("🚀"*30)
    
    print(f"\n📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Libros: {BOOKS_DIR}")
    print(f"📦 Índice ES: {ES_INDEX_NAME}")
    print(f"🧠 Embeddings: {EMBEDDING_MODEL} (OpenAI)\n")
    
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
        documents = load_documents()
        
        if not documents:
            print("❌ ERROR: No se cargaron documentos.")
            sys.exit(1)
        
        # 5. Dividir en chunks
        chunks = split_documents(documents)
        
        # 6. Indexar en Elasticsearch
        success = index_documents_to_elasticsearch(chunks)
        
        if not success:
            print("❌ ERROR: Fallo en la indexación")
            sys.exit(1)
        
        # 7. Verificar
        verify_index()
        
        # Resumen final
        print_header("✅ PROCESO COMPLETADO EXITOSAMENTE")
        print(f"📊 Resumen:")
        print(f"   - Documentos procesados: {len(documents)}")
        print(f"   - Chunks generados: {len(chunks)}")
        print(f"   - Índice Elasticsearch: {ES_INDEX_NAME}")
        print(f"   - Embeddings: OpenAI {EMBEDDING_MODEL}")
        print(f"\n🎯 Los usuarios ya pueden consultar este material desde la app.\n")
        
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