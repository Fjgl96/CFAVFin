# rag/financial_rag_elasticsearch.py
"""
⚠️ ⚠️ ⚠️ ADVERTENCIA - ARCHIVO OBSOLETO ⚠️ ⚠️ ⚠️

ESTE ARCHIVO YA NO SE USA EN EL PROYECTO PRINCIPAL.

El sistema RAG ahora se ejecuta como MICROSERVICIO independiente.
- El microservicio está en: https://rag-search-m70x.onrender.com
- La versión optimizada está en: rag/microservice_optimized.py

CONFIGURACIÓN ACTUAL:
- El proyecto principal hace llamadas HTTP al microservicio RAG
- Ver agents/financial_agents.py (línea 64-72) para el cliente
- Ver config.py (línea 137) para RAG_API_URL

SI NECESITAS ACTUALIZAR EL MICROSERVICIO:
1. Copia rag/microservice_optimized.py al proyecto del microservicio
2. Reinicia el servidor del microservicio

ESTE ARCHIVO SE MANTIENE SOLO COMO REFERENCIA/BACKUP.
NO MODIFICAR ESTE ARCHIVO - USAR microservice_optimized.py

===================================================================

Sistema RAG - VERSIÓN ELASTICSEARCH CON OPENAI EMBEDDINGS
Actualizado para LangChain 1.0+ con optimizaciones de rendimiento

Los usuarios consultan material financiero indexado en Elasticsearch.
El admin indexa documentos con generate_index.py
"""

from typing import List
from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from langchain_core.documents import Document
from langchain_core.tools import tool

# Importar configuración
from config_elasticsearch import (
    ES_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    get_elasticsearch_client,
    get_es_config
)

# Importar API key de OpenAI desde config principal
from config import OPENAI_API_KEY

# ========================================
# CLASE RAG ELASTICSEARCH
# ========================================

class FinancialRAGElasticsearch:
    """
    Sistema RAG usando Elasticsearch como vector store con OpenAI Embeddings.
    Solo lectura para usuarios.
    Actualizado para LangChain 1.0+
    """
    
    def __init__(
        self,
        index_name: str = ES_INDEX_NAME,
        embedding_model: str = EMBEDDING_MODEL
    ):
        self.index_name = index_name
        self.embedding_model_name = embedding_model
        
        # Verificar que existe API key
        if not OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY no encontrada. "
                "Configúrala en .env o Streamlit Secrets."
            )
        
        # Inicializar embeddings de OpenAI
        print(f"🧠 Cargando modelo de embeddings OpenAI: {embedding_model}")
        print(f"   Dimensiones: {EMBEDDING_DIMENSIONS}")
        
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=OPENAI_API_KEY,
            # Parámetros opcionales para optimización:
            chunk_size=1000,  # Número de textos por batch
            max_retries=3,
            timeout=30
        )
        
        # Vector store (se conecta a Elasticsearch)
        self.vector_store = None
        
        # Número de resultados a retornar
        self.k_results = 4
        
        # Conectar automáticamente
        self._connect()
    
    def _connect(self) -> bool:
        """Conecta al índice de Elasticsearch."""
        try:
            print(f"📥 Conectando a Elasticsearch (índice: {self.index_name})...")
            
            # Verificar que existe el cliente
            es_client = get_elasticsearch_client()
            if not es_client:
                print("❌ No se pudo conectar a Elasticsearch")
                return False
            
            # Verificar que existe el índice
            if not es_client.indices.exists(index=self.index_name):
                print(f"❌ El índice '{self.index_name}' no existe")
                print("   El administrador debe generar el índice primero:")
                print("   python admin/generate_index.py")
                return False
            
            # Obtener configuración
            es_config = get_es_config()
            
            # Crear ElasticsearchStore (LangChain 1.0 syntax)
            self.vector_store = ElasticsearchStore(
                index_name=self.index_name,
                embedding=self.embeddings,
                es_url=es_config["es_url"],
                es_user=es_config["es_user"],
                es_password=es_config["es_password"]
            )
            
            print(f"✅ Conectado a Elasticsearch (índice: {self.index_name})")
            
            # Mostrar info del índice
            count = es_client.count(index=self.index_name)
            print(f"   Documentos indexados: {count['count']}")
            
            return True
        
        except Exception as e:
            print(f"❌ Error conectando a Elasticsearch: {e}")
            return False

    def get_health_status(self) -> dict:
        """
        Retorna el estado de salud del sistema RAG.
        Determina el estado basado en el vector_store existente.
        """
        # Inferir estado actual
        is_connected = (
            self.vector_store is not None and
            self.embeddings is not None
        )
        
        # Inferir último error chequeando si _connect() falló
        error_msg = None
        if not is_connected:
            error_msg = "RAG no inicializado o conexión fallida"
        
        return {
            "connection_status": "connected" if is_connected else "disconnected",
            "last_error": error_msg,
            "retry_count": 0,  # No es crítico, solo para compatibilidad
            "index_name": self.index_name,
            "embeddings_loaded": self.embeddings is not None,
            "vector_store_ready": self.vector_store is not None
        }

    def search_documents(
        self,
        query: str,
        k: int = None,
        filter_dict: dict = None
    ) -> List[Document]:
        """
        Busca documentos similares a la query en Elasticsearch.
        
        Args:
            query: Consulta de búsqueda
            k: Número de documentos a retornar
            filter_dict: Filtros de metadata (ej: {"cfa_level": "I"})
        
        Returns:
            Lista de documentos relevantes
        """
        if k is None:
            k = self.k_results
        
        # Verificar que esté conectado
        if self.vector_store is None:
            print("⚠️ No conectado a Elasticsearch. Intentando reconectar...")
            if not self._connect():
                return []
        
        print(f"🔍 Buscando en Elasticsearch con OpenAI: '{query}' (top {k})")
        
        try:
            # Búsqueda semántica con similarity_search
            if filter_dict:
                results = self.vector_store.similarity_search(
                    query=query,
                    k=k,
                    filter=filter_dict
                )
            else:
                results = self.vector_store.similarity_search(
                    query=query,
                    k=k
                )
            
            print(f"✅ {len(results)} documentos encontrados")
            return results
        
        except Exception as e:
            print(f"❌ Error en búsqueda: {e}")
            return []


# ========================================
# INSTANCIA GLOBAL
# ========================================

# Instancia única del sistema RAG
rag_system = FinancialRAGElasticsearch()


# ========================================
# DICCIONARIO DE TÉRMINOS TÉCNICOS (ESPAÑOL ↔ INGLÉS)
# ========================================

TERMINOS_TECNICOS = {
    # ===== FINANZAS CORPORATIVAS =====
    "wacc": ["WACC", "Weighted Average Cost of Capital", "costo promedio ponderado", "costo de capital"],
    "van": ["NPV", "VAN", "Net Present Value", "Valor Actual Neto", "valor presente neto"],
    "tir": ["IRR", "TIR", "Internal Rate of Return", "tasa interna de retorno"],
    "payback": ["Payback Period", "periodo de recuperación", "payback"],
    "profitability_index": ["Profitability Index", "PI", "índice de rentabilidad", "índice de beneficio"],

    # ===== RENTA FIJA =====
    "bono": ["bond", "bono", "fixed income", "renta fija"],
    "cupón": ["coupon", "cupón"],
    "ytm": ["YTM", "yield to maturity", "rendimiento al vencimiento"],
    "duration": ["duration", "duración", "Macaulay duration", "modified duration", "duration modificada"],
    "convexity": ["convexity", "convexidad"],
    "current_yield": ["current yield", "rendimiento corriente", "yield"],
    "zero_coupon": ["zero-coupon bond", "bono cupón cero", "strip bond"],

    # ===== EQUITY =====
    "equity": ["equity", "acciones", "stock", "patrimonio"],
    "dividend": ["dividend", "dividendo"],
    "gordon": ["Gordon Growth", "modelo de Gordon", "dividend discount model", "DDM"],

    # ===== DERIVADOS =====
    "derivado": ["derivative", "derivado", "option", "opción"],
    "call": ["call option", "opción call"],
    "put": ["put option", "opción put"],
    "black-scholes": ["Black-Scholes", "Black Scholes"],
    "volatilidad": ["volatility", "volatilidad", "sigma"],
    "put_call_parity": ["put-call parity", "paridad put-call"],

    # ===== PORTAFOLIO =====
    "capm": ["CAPM", "Capital Asset Pricing Model", "modelo de valoración de activos"],
    "beta": ["beta", "systematic risk", "riesgo sistemático"],
    "sharpe": ["Sharpe ratio", "ratio de Sharpe", "rendimiento ajustado por riesgo"],
    "treynor": ["Treynor ratio", "ratio de Treynor", "índice de Treynor"],
    "jensen": ["Jensen's alpha", "Jensen alpha", "alfa de Jensen"],
    "portfolio": ["portfolio", "portafolio", "cartera"],
    "diversificación": ["diversification", "diversificación"],
    "correlación": ["correlation", "correlación", "covariance", "covarianza"],
    "riesgo": ["risk", "riesgo", "standard deviation", "desviación estándar"],
    "retorno": ["return", "retorno", "rendimiento", "expected return"],
}

# ========================================
# ÍNDICE INVERSO PARA TÉRMINOS TÉCNICOS
# ========================================

def _construir_indice_inverso() -> dict:
    """
    Construye índice inverso para búsqueda O(1) de términos técnicos.

    OPTIMIZACIÓN: En lugar de buscar O(n²) (palabra x término),
    creamos un índice {palabra_lower: [claves]} para búsqueda O(1).

    Returns:
        Dict mapping palabra -> lista de claves en TERMINOS_TECNICOS
    """
    indice = {}
    for key, synonyms in TERMINOS_TECNICOS.items():
        for term in synonyms:
            # Normalizar término (lower + split por espacios)
            palabras = term.lower().split()
            for palabra in palabras:
                if palabra not in indice:
                    indice[palabra] = []
                if key not in indice[palabra]:
                    indice[palabra].append(key)
    return indice

# Construir índice una sola vez al cargar el módulo
_INDICE_INVERSO = _construir_indice_inverso()
print(f"✅ Índice inverso construido: {len(_INDICE_INVERSO)} palabras -> términos técnicos")


def enriquecer_query_bilingue(consulta: str) -> str:
    """
    Enriquece la consulta agregando términos técnicos en inglés si se detectan en español.

    OPTIMIZACIÓN: Usa índice inverso para búsqueda O(1) en lugar de O(n²).

    Args:
        consulta: Query original del usuario (probablemente en español)

    Returns:
        Query enriquecida con términos bilingües
    """
    consulta_lower = consulta.lower()
    palabras_query = consulta_lower.split()

    # Buscar términos técnicos usando índice inverso (O(1) por palabra)
    claves_encontradas = set()
    for palabra in palabras_query:
        if palabra in _INDICE_INVERSO:
            claves_encontradas.update(_INDICE_INVERSO[palabra])

    # Si encontramos términos técnicos, agregar todos sus sinónimos
    if claves_encontradas:
        terminos_agregados = []
        for clave in claves_encontradas:
            terminos_agregados.extend(TERMINOS_TECNICOS[clave])

        # Eliminar duplicados manteniendo orden
        terminos_unicos = list(dict.fromkeys(terminos_agregados))
        terminos_str = " ".join(terminos_unicos)
        query_enriquecida = f"{consulta} {terminos_str}"
        print(f"🔄 Query enriquecida: '{consulta}' → agregados {len(terminos_unicos)} términos")
        return query_enriquecida

    return consulta


# ========================================
# HELPER: GENERAR VARIACIONES DE QUERY
# ========================================

def generar_variaciones_query(consulta: str) -> List[str]:
    """
    Genera variaciones de la query para búsqueda multi-query sin LLM.

    Estrategias:
    1. Query original (en español)
    2. Query enriquecida con términos bilingües
    3. Query con palabras clave extraídas (solo sustantivos técnicos)

    Args:
        consulta: Query original

    Returns:
        Lista de 2-3 variaciones de query
    """
    variaciones = []

    # Variación 1: Query original
    variaciones.append(consulta)

    # Variación 2: Query enriquecida con términos bilingües
    consulta_enriquecida = enriquecer_query_bilingue(consulta)
    if consulta_enriquecida != consulta:
        variaciones.append(consulta_enriquecida)

    # Variación 3: Extraer palabras clave (acrónimos y sustantivos técnicos) - OPTIMIZADO
    import re
    # Buscar acrónimos (2-5 letras mayúsculas)
    acronimos = re.findall(r'\b[A-Z]{2,5}\b', consulta)

    # Buscar palabras técnicas usando índice inverso (O(1) en lugar de O(n²))
    palabras_query = consulta.lower().split()
    palabras_tecnicas = []

    for palabra in palabras_query:
        if palabra in _INDICE_INVERSO:
            # Encontrar claves relacionadas
            for clave in _INDICE_INVERSO[palabra]:
                # Agregar primera variante (típicamente en inglés)
                first_synonym = TERMINOS_TECNICOS[clave][0]
                if first_synonym not in palabras_tecnicas:
                    palabras_tecnicas.append(first_synonym)

    # Combinar acrónimos + palabras técnicas
    if acronimos or palabras_tecnicas:
        query_keywords = " ".join(acronimos + palabras_tecnicas)
        if query_keywords and query_keywords not in variaciones:
            variaciones.append(query_keywords)

    return variaciones


def buscar_multi_query_paralelo(consulta: str, k_per_query: int = 2) -> List[Document]:
    """
    Ejecuta múltiples variaciones de búsqueda EN PARALELO y combina resultados.

    OPTIMIZACIONES:
    - Genera 2-3 variaciones de query SIN LLM adicional
    - Ejecuta búsquedas en paralelo usando ThreadPoolExecutor
    - Deduplica resultados con SHA256 (más robusto que hash())
    - Timeout de 10s por búsqueda para evitar colgarse
    - Retorna top-k más relevantes

    Args:
        consulta: Query original del usuario
        k_per_query: Documentos a buscar por cada variación (default: 2)

    Returns:
        Lista combinada de documentos únicos (max 4-6 resultados)
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
    import hashlib

    print(f"🚀 Multi-Query: Generando variaciones de '{consulta}'...")

    # Generar variaciones
    variaciones = generar_variaciones_query(consulta)
    print(f"   Variaciones generadas: {len(variaciones)}")
    for i, var in enumerate(variaciones, 1):
        print(f"   {i}. {var[:60]}...")

    # Ejecutar búsquedas en paralelo
    resultados_combinados = []
    contenidos_vistos = set()  # Para deduplicación

    def buscar_variacion(query_var):
        """Función helper para búsqueda en thread"""
        try:
            docs = rag_system.search_documents(query_var, k=k_per_query)
            return docs
        except Exception as e:
            print(f"❌ Error en búsqueda de variación '{query_var[:30]}...': {e}")
            return []

    print(f"🔍 Ejecutando {len(variaciones)} búsquedas en paralelo...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        # Enviar todas las búsquedas en paralelo
        future_to_query = {
            executor.submit(buscar_variacion, var): var
            for var in variaciones
        }

        # Recolectar resultados a medida que completan
        for future in as_completed(future_to_query):
            query_var = future_to_query[future]
            try:
                # OPTIMIZACIÓN: Agregar timeout de 10s para evitar colgarse
                docs = future.result(timeout=10)

                # Deduplicar por contenido
                for doc in docs:
                    # OPTIMIZACIÓN: Usar SHA256 en lugar de hash() para mejor unicidad
                    content_hash = hashlib.sha256(
                        doc.page_content.encode('utf-8')
                    ).hexdigest()

                    if content_hash not in contenidos_vistos:
                        contenidos_vistos.add(content_hash)
                        resultados_combinados.append(doc)

            except TimeoutError:
                print(f"⏱️ Timeout en búsqueda de '{query_var[:30]}...' (>10s)")
            except Exception as e:
                print(f"❌ Error procesando resultados de '{query_var[:30]}...': {e}")

    print(f"✅ Multi-Query completado: {len(resultados_combinados)} documentos únicos encontrados")

    # Retornar top-k resultados (máximo 6 para no saturar)
    return resultados_combinados[:6]


# ========================================
# TOOL PARA EL AGENTE
# ========================================

@tool
def buscar_documentacion_financiera(consulta: str) -> str:
    """
    Busca información en material financiero usando MULTI-QUERY INTELIGENTE.

    OPTIMIZACIÓN: Ejecuta 2-3 variaciones de búsqueda en PARALELO para mejorar recall
    sin aumentar latencia (búsquedas concurrentes vs secuenciales).

    Args:
        consulta: La pregunta o tema a buscar.

    Returns:
        Contexto relevante del material de estudio.
    """
    print(f"\n🔍 RAG Tool (Multi-Query) invocado con consulta: '{consulta}'")

    # OPTIMIZACIÓN: Multi-Query en paralelo (2-3 búsquedas concurrentes)
    docs = buscar_multi_query_paralelo(consulta, k_per_query=2)

    if not docs:
        return (
            "No encontré información relevante en el material de estudio indexado. "
            "Esto puede deberse a:\n"
            "1. El tema no está en el material indexado\n"
            "2. El índice no se ha generado aún en Elasticsearch\n"
            "3. Problema de conexión con Elasticsearch\n"
            "4. La consulta necesita reformularse\n\n"
            "Intenta reformular tu pregunta o consulta directamente al "
            "agente especializado correspondiente."
        )

    # Formatear resultado (limitado a 4 fragmentos para no saturar)
    context_parts = []
    for i, doc in enumerate(docs[:4], 1):  # Máximo 4 fragmentos
        source = doc.metadata.get('source', 'Desconocido')
        content = doc.page_content.strip()

        # Extraer nombre del archivo
        if source != 'Desconocido':
            from pathlib import Path
            source_name = Path(source).name
        else:
            source_name = source

        # Metadata adicional
        cfa_level = doc.metadata.get('cfa_level', 'N/A')

        context_parts.append(
            f"--- Fragmento {i} ---\n"
            f"Fuente: {source_name}\n"
            f"CFA Level: {cfa_level}\n"
            f"Contenido:\n{content}"
        )

    full_context = "\n\n".join(context_parts)

    return f"📚 Información encontrada en el material de estudio:\n\n{full_context}"


print("✅ Módulo financial_rag_elasticsearch cargado (LangChain 1.0, OpenAI Embeddings).")