# graph/agent_graph.py
"""
Grafo de agentes financieros.
Actualizado: Sincronizado con protocolos de financial_agents.py
"""

from typing import TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
import streamlit as st
from datetime import datetime
# graph/agent_graph.py

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage  # <--- Agregar SystemMessage
from pydantic import BaseModel, Field  # <--- Nuevo
from typing import Literal             # <--- Nuevo
from config import get_llm             # <--- Asegurar que esto esté importado



# Importar de config
from config import (
    CIRCUIT_BREAKER_MAX_RETRIES,
    CIRCUIT_BREAKER_COOLDOWN,
    ENABLE_POSTGRES_PERSISTENCE,
    get_postgres_uri
)

# Importar nodos de agente y supervisor
from agents.financial_agents import (
    supervisor_llm, supervisor_system_prompt,
    agent_nodes, RouterSchema
)

# Routing eliminado - ahora usamos clasificación LLM simple

# Importar logger
try:
    from utils.logger import get_logger
    logger = get_logger('graph')
except ImportError:
    import logging
    logger = logging.getLogger('graph')

# ========================================
# ESTADO DEL GRAFO
# ========================================

class AgentState(TypedDict):
    """Estado del grafo con tracking de errores mejorado."""
    messages: Annotated[list, lambda x, y: x + y]
    next_node: str
    error_count: int
    error_types: dict
    last_error_time: float
    circuit_open: bool

# ========================================
# HELPERS: DETECCIÓN DE ERRORES (ACTUALIZADO)
# ========================================
# graph/agent_graph.py

# === CLASE PARA SALIDA ESTRUCTURADA (SUPERVISOR v2) ===
class DecisionSupervisor(BaseModel):
    """Estructura de decisión del supervisor para clasificación y optimización."""
    categoria: Literal["TEORICA", "PRACTICA", "AYUDA"] = Field(
        description="Categoría de la intención del usuario: TEORICA (conceptos), PRACTICA (cálculos), AYUDA (soporte)."
    )
    query_optimizada: str = Field(
        description="La consulta del usuario reescrita y optimizada para búsqueda vectorial (traducida al inglés si es necesario, con términos técnicos CFA y sin ruido)."
    )
    razonamiento: str = Field(
        description="Breve justificación de la clasificación y optimización."
    )
def detect_error_type(message: AIMessage) -> str:
    """
    Detecta el tipo de error en un mensaje de agente.
    Sincronizado con las etiquetas de financial_agents.py
    """
    # Extraer contenido del mensaje
    full_content = ""
    if isinstance(message.content, str):
        full_content = message.content
    elif isinstance(message.content, list):
        for part in message.content:
            if isinstance(part, dict) and 'text' in part:
                full_content += part['text']
            elif isinstance(part, str):
                full_content += part
    
    # Normalizar a mayúsculas para buscar etiquetas
    content_upper = full_content.upper()
    
    # ✅ DETECTAR ÉXITO
    if 'TAREA_COMPLETADA' in content_upper:
        return 'success'
    
    # ❌ DETECTAR ERRORES BLOQUEANTES (Técnicos o Lógicos)
    if 'ERROR_BLOQUEANTE' in content_upper:
        return 'tool_failure'  # O 'blocking_error', lo mapeamos a tool_failure para simplificar
    
    # ⚠️ DETECTAR FALTA DE DATOS (Validación)
    if 'FALTAN_DATOS' in content_upper:
        return 'validation'
        
    # Fallback para errores no capturados por protocolo (legacy)
    content_lower = full_content.lower()
    if any(kw in content_lower for kw in ['error calculando', 'problema técnico', 'fallo herramienta']):
        return 'tool_failure'
    
    return 'unknown'


def should_open_circuit(error_types: dict, error_count: int) -> bool:
    """Determina si el circuit breaker debe activarse."""
    if error_types.get('tool_failure', 0) >= 2:
        logger.warning("🚨 Circuit breaker: Múltiples fallos de herramientas")
        return True
    
    if error_types.get('validation', 0) >= 3:
        logger.warning("🚨 Circuit breaker: Múltiples errores de validación")
        return True
    
    if error_count >= CIRCUIT_BREAKER_MAX_RETRIES:
        logger.warning("🚨 Circuit breaker: Límite total de errores alcanzado")
        return True
    
    return False


# ========================================
# NODO SUPERVISOR (HELPERS)
# ========================================

def _check_circuit_breaker_status(state: AgentState) -> dict:
    """Verifica el estado del circuit breaker."""
    circuit_open = state.get('circuit_open', False)
    error_count = state.get('error_count', 0)
    error_types = state.get('error_types', {})

    if circuit_open:
        logger.error("⛔ Circuit breaker ACTIVADO - finalizando ejecución")
        error_msg = (
            "🚨 **Sistema detenido por seguridad**\n\n"
            "El agente ha detectado inconsistencias repetidas.\n"
            f"**Errores:** {error_count} | **Tipos:** {error_types}\n\n"
            "Intenta reformular tu pregunta o proporcionar todos los datos necesarios."
        )
        return {
            "messages": [AIMessage(content=error_msg)],
            "next_node": "FINISH",
            "circuit_open": True
        }
    return None


def _analyze_last_message(messages: list) -> tuple:
    """Analiza el último mensaje para detectar errores."""
    possible_error_detected = False
    error_type = None
    error_count_delta = 0
    error_types_update = {}

    if messages and isinstance(messages[-1], AIMessage):
        last_message = messages[-1]
        if not getattr(last_message, 'tool_calls', []):
            error_type = detect_error_type(last_message)

            if error_type == 'success':
                logger.info("✅ Tarea completada exitosamente")
                possible_error_detected = False
            elif error_type in ['tool_failure', 'validation', 'capability']:
                possible_error_detected = True
                error_count_delta = 1
                error_types_update[error_type] = 1
                logger.warning(f"⚠️ Error detectado - Tipo: {error_type}")

    return possible_error_detected, error_type, error_count_delta, error_types_update


def _handle_circuit_breaker_activation(error_types: dict, error_count: int) -> dict:
    """Genera respuesta de activación del circuit breaker."""
    max_error_type = max(error_types, key=error_types.get) if error_types else 'unknown'

    if max_error_type == 'validation':
        error_msg = "⚠️ **Faltan Datos**: Por favor proporciona todos los parámetros requeridos."
    elif max_error_type == 'tool_failure':
        error_msg = "🔧 **Error Técnico**: Las herramientas no están respondiendo correctamente."
    else:
        error_msg = f"❌ **Procesamiento Detenido**: Demasiados reintentos ({error_count})."

    return {
        "messages": [AIMessage(content=error_msg)],
        "next_node": "FINISH",
        "circuit_open": True
    }


def _execute_routing_decision(state: AgentState, messages: list) -> tuple:
    """Ejecuta la lógica de routing usando supervisor LLM directo."""
    next_node_decision = "FINISH"
    routing_method = "supervisor_llm"
    routing_confidence = 0.95

    try:
        from agents.financial_agents import supervisor_llm, supervisor_system_prompt

        supervisor_messages = [HumanMessage(content=supervisor_system_prompt)] + messages
        route = supervisor_llm.invoke(supervisor_messages)

        next_node_decision = route.next_agent if hasattr(route, 'next_agent') else "FINISH"
        logger.info(f"🧭 Supervisor LLM decide: {next_node_decision}")

    except Exception as e:
        logger.error(f"❌ Error en supervisor: {e}", exc_info=True)
        next_node_decision = "FINISH"

    return next_node_decision, routing_method, routing_confidence


# ========================================
# NODO SUPERVISOR (PRINCIPAL)
# ========================================

def extraer_query_con_contexto(
    messages: list, 
    window_size: int = 2,
    categoria_actual: str = None  # ← NUEVO PARÁMETRO
) -> str:
    """
    Extrae la última query del usuario CON contexto limitado y FILTRADO.
    
    Args:
        messages: Historial completo
        window_size: Número de turnos previos a incluir (default: 2)
        categoria_actual: "TEORICA", "PRACTICA", o None
                         Si es "PRACTICA", filtra contexto teórico
    
    Returns:
        Query procesada (aislada o enriquecida con contexto relevante)
    """
    
    # 1. Encontrar última query del usuario
    last_user_msg = None
    last_user_idx = None
    
    for idx in range(len(messages) - 1, -1, -1):
        if isinstance(messages[idx], HumanMessage):
            last_user_msg = messages[idx].content
            last_user_idx = idx
            break
    
    if not last_user_msg:
        logger.warning("⚠️ No se encontró mensaje del usuario")
        return None
    
    # 2. Detectar si es un refinamiento (keywords clave)
    refinamiento_keywords = [
        "ahora", "pero", "con", "cambia", "modifica", "ajusta",
        "en vez", "en lugar", "si fuera", "qué pasa si",
        "y si", "con una", "con un", "usando"
    ]
    
    query_lower = last_user_msg.lower()
    es_refinamiento = any(kw in query_lower for kw in refinamiento_keywords)
    
    # 3. Si NO es refinamiento → Query aislada
    if not es_refinamiento:
        logger.info("📤 Query aislada (sin contexto)")
        return last_user_msg
    
    # 4. Si ES refinamiento → Incluir contexto limitado Y FILTRADO
    logger.info(f"📥 Extrayendo contexto (window={window_size}, cat={categoria_actual})")
    
    context_messages = []
    turn_count = 0
    
    for idx in range(last_user_idx - 1, -1, -1):
        msg = messages[idx]
        
        if isinstance(msg, HumanMessage):
            # ============================================================
            # FILTRADO: Solo contexto PRÁCTICO si categoría es PRACTICA
            # ============================================================
            
            if categoria_actual == "PRACTICA":
                msg_lower = msg.content.lower()
                
                # Keywords de preguntas teóricas (a filtrar)
                teoricas_keywords = [
                    "qué es", "que es", "define", "explica",
                    "cuál es", "cual es", "cómo se", "como se",
                    "significado", "concepto", "diferencia entre",
                    "para qué sirve", "por qué", "porque"
                ]
                
                es_pregunta_teorica = any(kw in msg_lower for kw in teoricas_keywords)
                
                if es_pregunta_teorica:
                    logger.info(f"⏭️ Saltando contexto teórico: '{msg.content[:50]}...'")
                    continue  # ← SALTAR mensaje teórico
            
            # Si pasa filtro, agregar
            context_messages.insert(0, f"Usuario: {msg.content}")
            turn_count += 1
            
            if turn_count >= window_size:
                break
                
        elif isinstance(msg, AIMessage):
            # Solo incluir respuesta si su pregunta fue incluida
            if context_messages and context_messages[-1].startswith("Usuario:"):
                content = msg.content[:200] + "..." if len(msg.content) > 200 else msg.content
                context_messages.insert(0, f"Asistente: {content}")
    
    # 5. Construir query enriquecida
    if context_messages:
        context_str = "\n".join(context_messages)
        enriched_query = f"""CONTEXTO PREVIO:
        {context_str}

        NUEVA CONSULTA:
        {last_user_msg}"""
                
        logger.info(f"✅ Query enriquecida ({len(enriched_query)} chars)")
        return enriched_query
    else:
        logger.info("⚠️ Sin contexto relevante, retornando query aislada")
        return last_user_msg
# graph/agent_graph.py


def supervisor_node(state: AgentState) -> dict:
    """
    Supervisor v5.0: Clasificación estructurada + Traducción RAG + Contexto inteligente.
    Soluciona el problema de definiciones matemáticas (ej: "mediana") y recupera la traducción al inglés.
    """
    logger.info("=" * 70)
    logger.info("--- SUPERVISOR v5.0 (DECISIÓN ESTRUCTURADA) ---")
    logger.info("=" * 70)
    
    messages = state.get('messages', [])
    error_count = state.get('error_count', 0)
    error_types = state.get('error_types', {})
    
    # 1. Circuit Breaker (Lógica existente preservada)
    cb_status = _check_circuit_breaker_status(state)
    if cb_status:
        return cb_status
    
    if not messages or not isinstance(messages[-1], HumanMessage):
        is_error, error_type, delta_count, delta_types = _analyze_last_message(messages)
        if is_error:
            error_count += delta_count
            for k, v in delta_types.items():
                error_types[k] = error_types.get(k, 0) + v
            if should_open_circuit(error_types, error_count):
                activation = _handle_circuit_breaker_activation(error_types, error_count)
                activation.update({"error_count": error_count, "error_types": error_types})
                return activation
        return {"next_node": "FINISH", "error_count": error_count, "error_types": error_types}
    
    # 2. Obtener Query Original y Contexto
    # Usamos tu helper 'extraer_query_con_contexto' para traer historial si es necesario (ej: refinamientos)
    last_user_query_raw = messages[-1].content
    
    # Pasamos categoria=None inicialmente para que traiga contexto conversacional si aplica
    query_con_contexto = extraer_query_con_contexto(messages, window_size=2, categoria_actual=None)
    if not query_con_contexto: 
        query_con_contexto = last_user_query_raw

    logger.info(f"📝 Contexto recuperado: {query_con_contexto[:100]}...")

    # 3. DECISIÓN ESTRUCTURADA (Clasificación + Traducción)
    # Aquí usamos la clase DecisionSupervisor que ya tienes definida en tu archivo
    
    system_prompt = """Eres el Supervisor Financiero CFA. 
    
    TU OBJETIVO:
    1. CLASIFICAR la intención del usuario con precisión quirúrgica.
    2. GENERAR una 'query_optimizada' para el siguiente paso.

    REGLAS DE CATEGORÍA:
    - TEORICA: Preguntas de "¿Qué es?", definiciones, conceptos, fórmulas o explicaciones.
      **CRÍTICO:** Preguntas sobre "mediana", "promedio", "WACC", "Beta" (sin pedir cálculo numérico explícito) son TEÓRICAS.
    - PRACTICA: Solicitudes EXPLÍCITAS de realizar un cálculo numérico con datos (ej: "Calcula el VAN", "Obtén el precio").
    - AYUDA: Saludos, agradecimientos o solicitudes de guía de uso.

    REGLAS DE 'query_optimizada':
    - Si es TEORICA: TRADUCE la intención principal a KEYWORDS EN INGLÉS para búsqueda vectorial eficiente.
      (Ej: "¿Qué es la mediana?" -> "Median definition statistics formula finance")
    - Si es PRACTICA: Mantén la query en ESPAÑOL y asegúrate de incluir los datos numéricos del contexto.
    """

    try:
        # Invocación estructurada usando tu clase Pydantic
        decision_llm = get_llm().with_structured_output(DecisionSupervisor)
        decision = decision_llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=query_con_contexto)
        ])
        
        categoria = decision.categoria
        query_final = decision.query_optimizada
        razonamiento = decision.razonamiento
        
        logger.info(f"🧠 Decisión: {categoria} | Razón: {razonamiento}")
        logger.info(f"🔍 Query Optimizada: {query_final}")

    except Exception as e:
        logger.error(f"❌ Error en decisión estructurada: {e}")
        # Fallback seguro ante error del LLM
        categoria = "PRACTICA"
        query_final = query_con_contexto

    # 4. ROUTING (Basado en la decisión estructurada)
    
    if categoria == "TEORICA":
        logger.info("📚 Ruteando a RAG (Keywords en Inglés)")
        return {
            "next_node": "Agente_RAG",
            "messages": [HumanMessage(content=query_final)], # Enviamos keywords en inglés
            "error_count": 0, 
            "error_types": {}
        }
    
    elif categoria == "AYUDA":
        logger.info("❓ Ruteando a Ayuda")
        return {
            "next_node": "Agente_Ayuda",
            "messages": [HumanMessage(content=query_con_contexto)],
            "error_count": 0, 
            "error_types": {}
        }
    
    else:  # PRACTICA
        logger.info("🧮 Ruteando a Especialista (Query en Español con datos)")
        
        # Clasificación de Nivel 2 para elegir el agente matemático correcto
        prompt_nivel2 = f"""Determina el agente especialista para esta consulta de cálculo.
        CONSULTA: {query_con_contexto}
        
        AGENTES:
        - Agente_Renta_Fija (Bonos, duration, convexity)
        - Agente_Finanzas_Corp (VAN, TIR, WACC)
        - Agente_Equity (Valuación acciones, Gordon)
        - Agente_Portafolio (CAPM, Sharpe, Mediana, Promedio, Estadísticas) <-- Nota: Estadística va aquí
        - Agente_Derivados (Opciones)

        Responde EXACTAMENTE: "Agente_XXXXX" """
        
        try:
            especialista_msg = get_llm().invoke([
                SystemMessage(content=prompt_nivel2),
                HumanMessage(content=query_con_contexto)
            ])
            next_node = especialista_msg.content.strip()
            
            # Validación de seguridad
            agentes_validos = [
                "Agente_Renta_Fija", "Agente_Finanzas_Corp",
                "Agente_Equity", "Agente_Portafolio", "Agente_Derivados"
            ]
            
            if next_node not in agentes_validos:
                logger.warning(f"⚠️ Respuesta L2 ambigua: '{next_node}'. Usando fallback por keywords.")
                # Fallback mejorado
                combined = query_con_contexto.lower()
                if "bono" in combined: next_node = "Agente_Renta_Fija"
                elif any(x in combined for x in ["capm", "beta", "mediana", "promedio", "desviación"]): 
                    next_node = "Agente_Portafolio" # <--- Agregamos mediana/promedio aquí por si acaso
                elif "opcion" in combined: next_node = "Agente_Derivados"
                else: next_node = "Agente_Finanzas_Corp"
            
            logger.info(f"🎯 Agente Seleccionado: {next_node}")
            
            return {
                "next_node": next_node,
                "messages": [HumanMessage(content=query_con_contexto)], # Mantenemos español para el agente
                "error_count": 0, 
                "error_types": {}
            }
            
        except Exception as e:
            logger.error(f"❌ Error en clasificación L2: {e}")
            return {
                "next_node": "Agente_Finanzas_Corp",
                "messages": [HumanMessage(content=query_con_contexto)],
                "error_count": error_count, 
                "error_types": error_types
            }
def build_graph():
    """Construye el grafo con persistencia."""
    logger.info("🏗️ Construyendo grafo...")
    workflow = StateGraph(AgentState)

    # Nodos
    workflow.add_node("Supervisor", supervisor_node)
    for name, node in agent_nodes.items():
        workflow.add_node(name, node)

    # Edges
    workflow.set_entry_point("Supervisor")
    
    def conditional_router(state):
        dest = state.get("next_node")
        return dest if dest in agent_nodes or dest == "FINISH" else "FINISH"

    conditional_map = {name: name for name in agent_nodes}
    conditional_map["FINISH"] = END

    workflow.add_conditional_edges("Supervisor", conditional_router, conditional_map)

    # Retornos
    for name in agent_nodes:
        if name in ["Agente_Ayuda", "Agente_RAG"]: 
            workflow.add_edge(name, END) # RAG y Ayuda terminan directo
        elif name == "Agente_Sintesis_RAG":
            workflow.add_edge(name, END)
        else:
            workflow.add_edge(name, "Supervisor")

    # Persistencia
    checkpointer = MemorySaver()
    if ENABLE_POSTGRES_PERSISTENCE:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver
            import psycopg_pool
            
            # 🔧 CORRECCIÓN: Configurar autocommit=True para permitir operaciones DDL (como crear índices)
            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }

            pool = psycopg_pool.ConnectionPool(
                conninfo=get_postgres_uri(), 
                min_size=1, 
                max_size=10,
                kwargs=connection_kwargs  # <-- Esto soluciona el error de transacción
            )
            
            checkpointer = PostgresSaver(pool)
            checkpointer.setup() # Crea las tablas si no existen
            logger.info("✅ PostgreSQL Persistence ON")
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL falló ({e}), usando MemorySaver")
    return workflow.compile(checkpointer=checkpointer)


# ========================================
# INICIALIZACIÓN DEL GRAFO
# ========================================

# Inicialización Global
try:
    compiled_graph = build_graph()
    logger.info("✅ Grafo compilado (routing simplificado con clasificación LLM)")
except Exception as e:
    logger.error(f"🔥 Error Fatal en Graph Init: {e}")
    st.error("Error crítico del sistema.")
    st.stop()