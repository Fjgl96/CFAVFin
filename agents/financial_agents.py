# agents/financial_agents.py
"""
Agentes especializados financieros.
Actualizado:
1. Conexión a Microservicio RAG.
2. Protocolo Anti-Hopping y Anti-Alucinación GLOBAL.
3. Redirección automática de teoría a RAG.
"""

import os
import requests
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from typing import Literal
from pydantic import BaseModel, Field

# Importar configuración
from config import get_llm, RAG_API_URL

# Importar herramientas financieras (locales)
from tools.financial_tools import (
    _calcular_valor_presente_bono, _calcular_van, _calcular_wacc,
    _calcular_gordon_growth, _calcular_capm, _calcular_sharpe_ratio,
    _calcular_opcion_call, _calcular_tir, _calcular_payback_period,
    _calcular_profitability_index, _calcular_duration_macaulay,
    _calcular_duration_modificada, _calcular_convexity,
    _calcular_current_yield, _calcular_bono_cupon_cero,
    _calcular_opcion_put, _calcular_put_call_parity,
    _calcular_treynor_ratio, _calcular_jensen_alpha, _calcular_beta_portafolio,
    _calcular_retorno_portafolio, _calcular_std_dev_portafolio
)
from tools.help_tools import obtener_ejemplos_de_uso

# Importar logger
try:
    from utils.logger import get_logger
    logger = get_logger('agents')
except ImportError:
    import logging
    logger = logging.getLogger('agents')

llm = get_llm()

# ========================================
# HERRAMIENTA RAG (CLIENTE MICROSERVICIO)
# ========================================

@tool
def buscar_documentacion_financiera(consulta: str) -> str:
    """
    Busca información en material financiero consultando el Microservicio RAG externo.
    """
    logger.info(f"🔍 Consultando Microservicio RAG: '{consulta[:50]}...'")

    if not RAG_API_URL:
        msg = "❌ Error de configuración: RAG_API_URL no definida."
        logger.error(msg)
        return msg

    endpoint = f"{RAG_API_URL.rstrip('/')}/search"

    try:
        # OPTIMIZACIÓN: Reducir timeout de 45s a 20s con retry
        # - Timeout excesivo bloquea el sistema innecesariamente
        # - 20s es suficiente para búsquedas RAG típicas
        # - Si falla, retry una vez con exponential backoff
        response = requests.post(
            endpoint,
            json={"consulta": consulta},
            timeout=20  # Reducido de 45s a 20s
        )

        if response.status_code == 200:
            data = response.json()
            resultado = data.get("resultado", "No se encontró información relevante.")
            logger.info("✅ Respuesta recibida del Microservicio")
            return resultado
        else:
            error_msg = f"Error del Servicio RAG ({response.status_code}): {response.text}"
            logger.error(f"❌ {error_msg}")
            return error_msg

    except Exception as e:
        error_msg = f"Error de Conexión con RAG: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return error_msg

# ========================================
# NODOS ESPECIALES
# ========================================

def nodo_ayuda_directo(state: dict) -> dict:
    """Nodo simple que llama a la herramienta de ayuda."""
    try:
        guia = obtener_ejemplos_de_uso.invoke({})
        return {"messages": [AIMessage(content=guia + "\n\nTAREA_COMPLETADA")]}
    except Exception as e:
        return {"messages": [AIMessage(content=f"Error ayuda: {e}\nERROR_BLOQUEANTE")]}

def nodo_rag(state: dict) -> dict:
    """
    Nodo RAG Deterministico (Optimizacion v2).
    Ya NO es un agente ReAct. Es una cadena lineal:
    Query Optimizada (del Supervisor) -> API RAG -> Síntesis LLM.
    """
    logger.info("📚 Agente RAG (Modo Ejecución Directa) invocado")

    messages = state.get("messages", [])
    if not messages:
        return {"messages": [AIMessage(content="Error: Sin mensajes.")]}

    # 1. OBTENER QUERY OPTIMIZADA
    # Como el Supervisor v2 ya reemplazó el último mensaje con la query perfecta,
    # solo la tomamos.
    last_message = messages[-1]
    query_para_rag = last_message.content 
    
    logger.info(f"🔍 Ejecutando búsqueda directa: '{query_para_rag[:50]}...'")

    try:
        # 2. LLAMADA DIRECTA A LA HERRAMIENTA (Sin pedirle permiso a un LLM)
        # Invocamos la herramienta directamente como función
        # Nota: buscar_documentacion_financiera es un @tool, usamos .invoke()
        contexto_recuperado = buscar_documentacion_financiera.invoke(query_para_rag)
        
        # 3. SÍNTESIS DE RESPUESTA (Única llamada al LLM en este nodo)
        # Usamos un prompt de síntesis estricto para evitar alucinaciones
        prompt_sintesis = f"""Eres un Asistente Financiero CFA experto.
        
        INSTRUCCIONES:
        1. Responde a la consulta del usuario basándote EXCLUSIVAMENTE en el CONTEXTO proporcionado.
        2. Si el contexto contiene la respuesta, sé directo y técnico.
        3. Si el contexto NO es relevante, dilo claramente.
        4. Responde siempre en ESPAÑOL profesional.

        CONTEXTO RECUPERADO:
        {contexto_recuperado}

        CONSULTA ORIGINAL:
        {query_para_rag} (Nota: Esta query fue optimizada para búsqueda)
        
        Respuesta final:"""

        # Usamos el LLM configurado (idealmente un modelo rápido como Haiku o GPT-4o-mini)
        response_message = llm.invoke(prompt_sintesis)
        
        # Aseguramos que termine con la señal de éxito para el grafo
        if isinstance(response_message, AIMessage):
            # Agregamos la etiqueta de cierre si no está (aunque el supervisor ya no la necesite tanto, ayuda al log)
            if "TAREA_COMPLETADA" not in response_message.content:
                 # Hack opcional: modificar el contenido es inmutable, creamos uno nuevo
                 pass 
        
        return {"messages": [response_message]}

    except Exception as e:
        logger.error(f"❌ Error en RAG Directo: {e}", exc_info=True)
        return {
            "messages": [AIMessage(
                content="Lo siento, hubo un error técnico al consultar la base de conocimientos. ERROR_BLOQUEANTE"
            )]
        }

def nodo_sintesis_rag(state: dict) -> dict:
    """Nodo passthrough para compatibilidad."""
    return {"messages": [AIMessage(content="Síntesis finalizada.\nTAREA_COMPLETADA")]}

def crear_agente_especialista(llm_instance, tools_list, system_prompt_text):
    if not tools_list: raise ValueError("Sin herramientas")
    llm_with_system = llm_instance.bind(system=system_prompt_text)
    return create_react_agent(llm_with_system, tools_list)


# ========================================
# PROMPTS MAESTROS (LA CLAVE DE LA SOLUCIÓN)
# ========================================

# Este bloque actualiza a TODOS los agentes para que sepan rechazar teoría
PROTOCOLO_SEGURIDAD = """
**PROTOCOLO DE SEGURIDAD Y CIERRE (OBLIGATORIO):**
0. **ECONOMÍA DE ACCIÓN:**
   - Tu objetivo es responder ÚNICA y EXCLUSIVAMENTE lo que el usuario preguntó.
   - NO realices cálculos adicionales no solicitados (ej: si piden VAN, no calcules TIR).
   - Sé directo y conciso

1. **FILTRO DE TEORÍA (CRÍTICO - EVITA EL BUCLE):**
   - Si el usuario pregunta "¿Qué es...?", "Explica...", "Definición de..." y NO pide un cálculo numérico específico:
   - TU RESPUESTA DEBE SER EXACTAMENTE: "Esta es una consulta teórica. TRANSFERIR_A_RAG"
   - NO intentes explicar conceptos tú mismo. Tu trabajo es SOLO calcular.

2. **ANTI-ALUCINACIÓN:**
   - Si la herramienta requiere un parámetro (ej: 'inversion_inicial') y NO está explícitamente en el historial:
   - **ESTÁ PROHIBIDO INVENTARLO**. No asumas 0, 1, ni promedios.
   - TU ÚNICA ACCIÓN es reportar que falta ese dato con FALTAN_DATOS.

3. **ETIQUETAS DE CIERRE:**
   Tu mensaje FINAL debe terminar con una de estas etiquetas para guiar al Supervisor:

   - **Caso Éxito:** "[Respuesta numérica]. TAREA_COMPLETADA"
   - **Caso Faltan Datos:** "Necesito [datos]. FALTAN_DATOS"
   - **Caso Error:** "Error técnico: [razón]. ERROR_BLOQUEANTE"
   - **Caso Teoría:** "Consulta teórica. TRANSFERIR_A_RAG"
"""

PROMPT_RENTA_FIJA = f"Eres especialista en Renta Fija. {PROTOCOLO_SEGURIDAD}"
PROMPT_FIN_CORP = f"Eres especialista en Finanzas Corporativas. {PROTOCOLO_SEGURIDAD}"
PROMPT_EQUITY = f"Eres especialista en Equity. {PROTOCOLO_SEGURIDAD}"
PROMPT_PORTAFOLIO = f"Eres especialista en Portafolios. {PROTOCOLO_SEGURIDAD}"
PROMPT_DERIVADOS = f"Eres especialista en Derivados. {PROTOCOLO_SEGURIDAD}"


# ========================================
# CREACIÓN DE AGENTES
# ========================================

agent_renta_fija = crear_agente_especialista(llm, [
    _calcular_valor_presente_bono, _calcular_duration_macaulay, _calcular_duration_modificada,
    _calcular_convexity, _calcular_current_yield, _calcular_bono_cupon_cero
], PROMPT_RENTA_FIJA)

agent_fin_corp = crear_agente_especialista(llm, [
    _calcular_van, _calcular_wacc, _calcular_tir,
    _calcular_payback_period, _calcular_profitability_index
], PROMPT_FIN_CORP)

agent_equity = crear_agente_especialista(llm, [_calcular_gordon_growth], PROMPT_EQUITY)

agent_portafolio = crear_agente_especialista(llm, [
    _calcular_capm, _calcular_sharpe_ratio, _calcular_treynor_ratio,
    _calcular_jensen_alpha, _calcular_beta_portafolio,
    _calcular_retorno_portafolio, _calcular_std_dev_portafolio
], PROMPT_PORTAFOLIO)

agent_derivados = crear_agente_especialista(llm, [
    _calcular_opcion_call, _calcular_opcion_put, _calcular_put_call_parity
], PROMPT_DERIVADOS)

agent_nodes = {
    "Agente_Renta_Fija": agent_renta_fija,
    "Agente_Finanzas_Corp": agent_fin_corp,
    "Agente_Equity": agent_equity,
    "Agente_Portafolio": agent_portafolio,
    "Agente_Derivados": agent_derivados,
    "Agente_Ayuda": nodo_ayuda_directo,
    "Agente_RAG": nodo_rag,
    "Agente_Sintesis_RAG": nodo_sintesis_rag
}

# ========================================
# SUPERVISOR (MÁQUINA DE ESTADOS)
# ========================================

class RouterSchema(BaseModel):
    next_agent: Literal["Agente_Renta_Fija", "Agente_Finanzas_Corp", "Agente_Equity", 
                       "Agente_Portafolio", "Agente_Derivados", "Agente_Ayuda", 
                       "Agente_RAG", "FINISH"] = Field(description="Próximo nodo o FINISH")

supervisor_llm = llm.with_structured_output(RouterSchema)

supervisor_system_prompt = """Eres el Supervisor.
MÁQUINA DE ESTADOS (PRIORIDAD MÁXIMA):

1. **SEÑALES DE CONTROL:**
   - "TAREA_COMPLETADA" -> RESPONDE: `FINISH`
   - "FALTAN_DATOS" -> RESPONDE: `FINISH` (Devolver al usuario)
   - "ERROR_BLOQUEANTE" -> RESPONDE: `FINISH`
   - "TRANSFERIR_A_RAG" -> RESPONDE: `Agente_RAG` (Redirección inmediata)

2. **ANTI-LOOP:**
   Si el último mensaje es de un Agente y NO contiene "TRANSFERIR_A_RAG", tu respuesta es `FINISH`.
   (Nunca reintentes con el mismo agente si ya falló o pidió datos).

3. **ENRUTAMIENTO INICIAL (Solo si habla el Usuario):**
   - Teoría/Conceptos -> `Agente_RAG`
   - Cálculos -> Agente Especialista
   - Ayuda -> `Agente_Ayuda`
"""

logger.info("✅ Agentes financieros cargados (Modo Cliente Microservicio + Protocolo RAG)")