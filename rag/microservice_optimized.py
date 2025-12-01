# rag/financial_rag_elasticsearch.py
"""
Sistema RAG - VERSIÓN OPTIMIZADA PARA MICROSERVICIO
Incluye todas las optimizaciones de rendimiento implementadas

INSTRUCCIONES:
1. Copia este archivo al proyecto del microservicio
2. Reemplaza el archivo financial_rag_elasticsearch.py existente
3. Reinicia el servidor del microservicio

OPTIMIZACIONES INCLUIDAS:
- Índice inverso O(1) para términos técnicos
- Multi-query paralelo con timeout
- Deduplicación robusta con SHA256
- Mejor manejo de errores
"""

from typing import List
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
import hashlib
import re

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import OpenAIEmbeddings
from langchain_elasticsearch import ElasticsearchStore
from langchain_core.documents import Document
from langchain_core.tools import tool

from config_elasticsearch import (
    ES_INDEX_NAME,
    EMBEDDING_MODEL,
    get_elasticsearch_client,
    get_es_config
)
from config import OPENAI_API_KEY


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


# ========================================
# CLASE RAG ELASTICSEARCH OPTIMIZADA
# ========================================

class FinancialRAGElasticsearch:
    """
    Sistema RAG optimizado para microservicio.

    OPTIMIZACIONES:
    - Índice inverso para enriquecimiento de queries
    - Multi-query paralelo con timeout
    - Deduplicación robusta con SHA256
    - Mejor manejo de errores y reintentos
    """

    def __init__(self, index_name: str = ES_INDEX_NAME, embedding_model: str = EMBEDDING_MODEL):
        self.index_name = index_name

        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY no configurada.")

        print(f"🧠 Cargando modelo de embeddings: {embedding_model}")
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=OPENAI_API_KEY,
            chunk_size=1000,
            max_retries=3,
            timeout=30
        )

        self.vector_store = None
        self._connect()

    def _connect(self) -> bool:
        """Conecta al índice de Elasticsearch."""
        try:
            es_client = get_elasticsearch_client()
            if not es_client:
                print("❌ No se pudo conectar a Elasticsearch")
                return False

            # Verificar que existe el índice
            if not es_client.indices.exists(index=self.index_name):
                print(f"❌ El índice '{self.index_name}' no existe")
                return False

            es_config = get_es_config()

            # Configuración dinámica para Cloud ID o URL
            store_kwargs = {
                "index_name": self.index_name,
                "embedding": self.embeddings,
                "es_user": es_config["es_user"],
                "es_password": es_config["es_password"]
            }

            if "es_cloud_id" in es_config:
                store_kwargs["es_cloud_id"] = es_config["es_cloud_id"]
            else:
                store_kwargs["es_url"] = es_config.get("es_url")

            self.vector_store = ElasticsearchStore(**store_kwargs)

            # Mostrar info del índice
            count = es_client.count(index=self.index_name)
            print(f"✅ RAG conectado a índice: {self.index_name}")
            print(f"   Documentos indexados: {count['count']}")

            return True

        except Exception as e:
            print(f"❌ Error conectando a Elasticsearch: {e}")
            return False

    def search_documents(self, query: str, k: int = 4) -> List[Document]:
        """
        Búsqueda básica de documentos (sin multi-query).
        """
        if not self.vector_store:
            if not self._connect():
                return []

        try:
            print(f"🔍 Buscando: '{query}' (top {k})")
            results = self.vector_store.similarity_search(query=query, k=k)
            print(f"✅ {len(results)} documentos encontrados")
            return results
        except Exception as e:
            print(f"❌ Error en búsqueda: {e}")
            return []

    def enriquecer_query_bilingue(self, consulta: str) -> str:
        """
        Enriquece la consulta con términos técnicos bilingües.

        OPTIMIZACIÓN: Usa índice inverso O(1) en lugar de búsqueda O(n²).
        """
        consulta_lower = consulta.lower()
        palabras_query = consulta_lower.split()

        # Buscar términos técnicos usando índice inverso
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
            print(f"🔄 Query enriquecida: '{consulta}' → +{len(terminos_unicos)} términos")
            return query_enriquecida

        return consulta

    def generar_variaciones_query(self, consulta: str) -> List[str]:
        """
        Genera variaciones de la query para multi-query.

        OPTIMIZACIÓN: Usa índice inverso para extracción rápida de keywords.
        """
        variaciones = []

        # Variación 1: Query original
        variaciones.append(consulta)

        # Variación 2: Query enriquecida
        consulta_enriquecida = self.enriquecer_query_bilingue(consulta)
        if consulta_enriquecida != consulta:
            variaciones.append(consulta_enriquecida)

        # Variación 3: Keywords (acrónimos + términos técnicos)
        acronimos = re.findall(r'\b[A-Z]{2,5}\b', consulta)

        # Extraer palabras técnicas con índice inverso
        palabras_query = consulta.lower().split()
        palabras_tecnicas = []

        for palabra in palabras_query:
            if palabra in _INDICE_INVERSO:
                for clave in _INDICE_INVERSO[palabra]:
                    first_synonym = TERMINOS_TECNICOS[clave][0]
                    if first_synonym not in palabras_tecnicas:
                        palabras_tecnicas.append(first_synonym)

        if acronimos or palabras_tecnicas:
            query_keywords = " ".join(acronimos + palabras_tecnicas)
            if query_keywords and query_keywords not in variaciones:
                variaciones.append(query_keywords)

        return variaciones

    def buscar_multi_query_paralelo(self, consulta: str, k_per_query: int = 2) -> List[Document]:
        """
        Multi-query paralelo OPTIMIZADO.

        OPTIMIZACIONES:
        - Búsquedas en paralelo con ThreadPoolExecutor
        - Timeout de 10s por búsqueda
        - Deduplicación robusta con SHA256
        - Mejor manejo de errores
        """
        print(f"🚀 Multi-Query: '{consulta}'")

        # Generar variaciones
        variaciones = self.generar_variaciones_query(consulta)
        print(f"   Variaciones: {len(variaciones)}")
        for i, var in enumerate(variaciones, 1):
            print(f"   {i}. {var[:60]}...")

        # Ejecutar búsquedas en paralelo
        resultados_combinados = []
        contenidos_vistos = set()

        def buscar_variacion(query_var):
            """Helper para búsqueda en thread"""
            try:
                return self.search_documents(query_var, k=k_per_query)
            except Exception as e:
                print(f"❌ Error en variación '{query_var[:30]}...': {e}")
                return []

        print(f"🔍 Ejecutando {len(variaciones)} búsquedas en paralelo...")

        with ThreadPoolExecutor(max_workers=3) as executor:
            future_to_query = {
                executor.submit(buscar_variacion, var): var
                for var in variaciones
            }

            # Recolectar resultados con timeout
            for future in as_completed(future_to_query):
                query_var = future_to_query[future]
                try:
                    # OPTIMIZACIÓN: Timeout de 10s
                    docs = future.result(timeout=10)

                    # Deduplicar con SHA256
                    for doc in docs:
                        content_hash = hashlib.sha256(
                            doc.page_content.encode('utf-8')
                        ).hexdigest()

                        if content_hash not in contenidos_vistos:
                            contenidos_vistos.add(content_hash)
                            resultados_combinados.append(doc)

                except TimeoutError:
                    print(f"⏱️ Timeout en '{query_var[:30]}...'")
                except Exception as e:
                    print(f"❌ Error procesando '{query_var[:30]}...': {e}")

        print(f"✅ Multi-Query: {len(resultados_combinados)} docs únicos")
        return resultados_combinados[:6]


# ========================================
# INSTANCIA GLOBAL
# ========================================

rag_system = FinancialRAGElasticsearch()


# ========================================
# TOOL PARA COMPATIBILIDAD
# ========================================

@tool
def buscar_documentacion_financiera(consulta: str, use_multi_query: bool = True) -> str:
    """
    Busca en documentación financiera.

    Args:
        consulta: Query del usuario
        use_multi_query: Si True, usa multi-query paralelo (recomendado)

    Returns:
        Contexto formateado
    """
    print(f"\n🔍 RAG Tool invocado: '{consulta}'")
    print(f"   Multi-query: {use_multi_query}")

    # Seleccionar estrategia de búsqueda
    if use_multi_query:
        docs = rag_system.buscar_multi_query_paralelo(consulta, k_per_query=2)
    else:
        docs = rag_system.search_documents(consulta, k=4)

    if not docs:
        return (
            "No se encontró información relevante en la base de datos. "
            "Intenta reformular tu pregunta o consulta directamente al "
            "agente especializado correspondiente."
        )

    # Formatear resultado
    context_parts = []
    for i, doc in enumerate(docs[:4], 1):
        nombre_fuente = doc.metadata.get('source', 'Desconocido')

        # Limpieza del nombre
        if "/" in str(nombre_fuente) or "\\" in str(nombre_fuente):
            nombre_fuente = os.path.basename(str(nombre_fuente))

        cfa_level = doc.metadata.get('cfa_level', 'N/A')

        context_parts.append(
            f"--- Fragmento {i} ---\n"
            f"Fuente: {nombre_fuente}\n"
            f"CFA Level: {cfa_level}\n"
            f"Contenido:\n{doc.page_content.strip()}"
        )

    return f"📚 Información encontrada:\n\n" + "\n\n".join(context_parts)


print("✅ Módulo RAG optimizado cargado (Multi-query + Índice inverso)")
