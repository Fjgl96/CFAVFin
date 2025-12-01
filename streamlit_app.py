# streamlit_app.py
"""
Aplicación Streamlit - Agente Financiero con RAG.
Actualizado para LangChain 1.0+ con:
- Health checks al inicio
- UI mejorada con métricas
- Logging estructurado
- Mejor manejo de errores
"""

import streamlit as st
from langchain_core.messages import HumanMessage, AIMessage
import uuid
from datetime import datetime

# Importar logger
try:
    from utils.logger import get_logger, log_system_event
    logger = get_logger('streamlit')
except ImportError:
    import logging
    logger = logging.getLogger('streamlit')

# ========================================
# CONFIGURACIÓN DE PÁGINA
# ========================================

st.set_page_config(
    page_title="Agente Financiero Pro",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="auto"
)

# ========================================
# HEALTH CHECK SYSTEM
# ========================================

@st.cache_resource(show_spinner=False)
def verify_system_health():
    """
    Verifica que todos los componentes críticos estén operativos.
    
    Returns:
        Diccionario con estado de cada componente
    """
    logger.info("🔍 Iniciando health checks del sistema...")
    
    health_status = {
        "config": {"status": False, "details": ""},
        "llm": {"status": False, "details": ""},
        "rag": {"status": False, "details": ""},
        "graph": {"status": False, "details": ""},
        "tools": {"status": False, "details": ""}
    }
    
    # Check 1: Configuración
    try:
        from config import ANTHROPIC_API_KEY, ES_URL, ES_INDEX_NAME
        health_status["config"]["status"] = True
        health_status["config"]["details"] = f"ES: {ES_INDEX_NAME}"
        logger.info("✅ Config cargado")
    except Exception as e:
        health_status["config"]["details"] = str(e)
        logger.error(f"❌ Config falló: {e}")
    
    # Check 2: LLM
    try:
        from config import get_llm
        llm = get_llm()
        # Test rápido
        test_response = llm.invoke("test")
        health_status["llm"]["status"] = True
        health_status["llm"]["details"] = "Claude 3.5 Haiku"
        logger.info("✅ LLM funcional")
    except Exception as e:
        health_status["llm"]["details"] = str(e)
        logger.error(f"❌ LLM falló: {e}")
    
    # Check 3: RAG Microservice
    # OPTIMIZACIÓN: Ahora RAG es microservicio, hacemos health check al endpoint
    try:
        from config import RAG_API_URL
        import requests

        if RAG_API_URL:
            # Intentar ping al microservicio con timeout corto
            health_endpoint = f"{RAG_API_URL.rstrip('/')}/health"
            try:
                response = requests.get(health_endpoint, timeout=5)
                if response.status_code == 200:
                    health_status["rag"]["status"] = True
                    health_status["rag"]["details"] = f"Microservicio OK ({RAG_API_URL})"
                    logger.info(f"✅ RAG Microservicio: OK")
                else:
                    health_status["rag"]["details"] = f"HTTP {response.status_code}"
                    logger.warning(f"⚠️ RAG Microservicio: HTTP {response.status_code}")
            except requests.exceptions.Timeout:
                health_status["rag"]["details"] = "Timeout (>5s)"
                logger.warning("⚠️ RAG Microservicio: Timeout")
            except requests.exceptions.ConnectionError:
                health_status["rag"]["details"] = "No se pudo conectar"
                logger.warning("⚠️ RAG Microservicio: Sin conexión")
        else:
            health_status["rag"]["details"] = "RAG_API_URL no configurada"
            logger.warning("⚠️ RAG_API_URL no configurada")
    except Exception as e:
        health_status["rag"]["details"] = str(e)
        logger.error(f"❌ RAG health check falló: {e}")
    
    # Check 4: Grafo
    try:
        from graph.agent_graph import compiled_graph
        health_status["graph"]["status"] = True
        health_status["graph"]["details"] = "LangGraph compilado"
        logger.info("✅ Grafo cargado")
    except Exception as e:
        health_status["graph"]["details"] = str(e)
        logger.error(f"❌ Grafo falló: {e}")
        st.error(f"Error crítico al importar el agente: {e}")
        st.stop()
    
    # Check 5: Tools
    try:
        from tools.financial_tools import financial_tool_list
        tool_count = len(financial_tool_list)
        health_status["tools"]["status"] = tool_count == 22
        health_status["tools"]["details"] = f"{tool_count}/22 herramientas"
        logger.info(f"✅ Tools cargados: {tool_count}")
    except Exception as e:
        health_status["tools"]["details"] = str(e)
        logger.error(f"❌ Tools fallaron: {e}")
    
    # Log evento de inicio
    log_system_event('startup', details=health_status)
    
    return health_status


# ========================================
# EJECUTAR HEALTH CHECKS
# ========================================

with st.spinner("🔍 Verificando sistemas..."):
    health = verify_system_health()

# Importar grafo después de health check
from graph.agent_graph import compiled_graph
from config import LANGSMITH_ENABLED
import os

# ========================================
# HEADER Y STATUS
# ========================================

st.title("Compañero de estudio")
st.caption("Con LangGraph, Claude 3.5 Haiku y RAG (Elasticsearch)")

# Mostrar LangSmith status
if LANGSMITH_ENABLED:
    st.info(f"🔍 **LangSmith activo** - Proyecto: `{os.environ.get('LANGCHAIN_PROJECT', 'N/A')}`")

# ========================================
# SIDEBAR: SYSTEM STATUS
# ========================================

with st.sidebar:
    st.header("📊 Estado del Sistema")
    
    # Métricas de componentes
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(
            "LLM",
            "✅ OK" if health["llm"]["status"] else "❌ Error",
            delta=health["llm"]["details"] if health["llm"]["status"] else None
        )
        st.metric(
            "Grafo",
            "✅ OK" if health["graph"]["status"] else "❌ Error",
            delta=None
        )
        st.metric(
            "Config",
            "✅ OK" if health["config"]["status"] else "❌ Error",
            delta=None
        )
    
    with col2:
        st.metric(
            "RAG",
            "✅ OK" if health["rag"]["status"] else "⚠️ Offline",
            delta=health["rag"]["details"][:20] if not health["rag"]["status"] else "Elasticsearch"
        )
        st.metric(
            "Tools",
            "✅ OK" if health["tools"]["status"] else "❌ Error",
            delta=health["tools"]["details"]
        )
    
    # Advertencias si algo falla
    if not health["rag"]["status"]:
        st.warning("**Revisar**\n\n")
    
    if not all(h["status"] for h in [health["llm"], health["graph"], health["tools"]]):
        st.error("❌ **Sistema parcialmente funcional**\n\nAlgunos componentes tienen problemas.")
    
    st.divider()
    
    # Info de sesión
    if "thread_id" in st.session_state:
        st.caption(f"🔑 Session: {st.session_state.thread_id[:8]}...")
    
    st.caption(f"⏰ {datetime.now().strftime('%H:%M:%S')}")

# ========================================
# MAIN CONTENT
# ========================================

st.markdown("""
Esta es una calculadora financiera inteligente con acceso a material de estudio. Puedes:

**📊 Realizar cálculos financieros (22 herramientas CFA Level I):**
- **Renta Fija:** Valoración de Bonos, Duration, Convexity, Current Yield
- **Finanzas Corporativas:** VAN, WACC, TIR, Payback Period, Profitability Index
- **Portafolio:** CAPM, Sharpe/Treynor/Jensen, Beta, Retorno, Desviación Estándar
- **Equity:** Gordon Growth Model
- **Derivados:** Opciones Call/Put (Black-Scholes), Put-Call Parity

**📚 Consultar material de estudio financiero:**
- "¿Qué es el WACC?"
- "Explica el concepto de Duration"
- "Busca información sobre el modelo Gordon Growth"

**❓ Obtener ayuda:**
- "Ayuda" o "¿Qué puedes hacer?"
""")
st.divider()

# ========================================
# CHAT LOGIC
# ========================================

# Inicializar historial
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "¡Hola! ¿Qué cálculo financiero necesitas realizar hoy? También puedo consultar material de estudio si tienes preguntas teóricas."}
    ]
    logger.info("💬 Nueva sesión de chat iniciada")

# Inicializar thread_id
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
    logger.info(f"🆔 Thread ID generado: {st.session_state.thread_id}")

# Mostrar historial
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
# ========================================
# USER INPUT
# ========================================

if prompt := st.chat_input("Ej: Calcula VAN: inversión 50k, flujos [15k, 20k, 25k], tasa 12%"):
    
    # Agregar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    logger.info(f"👤 Usuario: {prompt[:100]}...")
    
    # Preparar entrada para LangGraph
    graph_input = {"messages": [HumanMessage(content=prompt)]}
    config = {"configurable": {"thread_id": st.session_state.thread_id}}
    
    # Ejecutar grafo
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        
        with st.spinner("🧠 Procesando..."):
            final_response_content = ""
            
            try:
                # Log inicio de procesamiento
                log_system_event('query', details={
                    'query': prompt[:200],
                    'thread_id': st.session_state.thread_id
                })
                
                # Invocar grafo
                final_state = compiled_graph.invoke(graph_input, config=config)
                
                # Extraer respuesta final
                if final_state and "messages" in final_state and final_state["messages"]:
                    for msg in reversed(final_state["messages"]):
                        is_final_ai_msg = isinstance(msg, AIMessage) and not getattr(msg, 'tool_calls', [])
                        if is_final_ai_msg:
                            content = msg.content
                            if isinstance(content, str):
                                final_response_content = content
                            elif isinstance(content, list):
                                text_parts = []
                                for part in content:
                                    if isinstance(part, dict) and 'text' in part:
                                        text_parts.append(part['text'])
                                    elif isinstance(part, str):
                                        text_parts.append(part)
                                final_response_content = "\n".join(text_parts).strip()
                            
                            if final_response_content:
                                break
                
                if not final_response_content:
                    final_response_content = (
                        "Lo siento, no pude procesar tu solicitud completamente. "
                        "¿Podrías reformular o proporcionar más detalles?"
                    )
                    logger.warning("⚠️ No se encontró respuesta final válida")
                
                logger.info(f"✅ Respuesta generada ({len(final_response_content)} chars)")
            
            except Exception as e:
                final_response_content = (
                    "❌ Ocurrió un error inesperado al procesar tu solicitud. "
                    "Por favor, intenta de nuevo."
                )
                logger.error(f"❌ Error en runtime: {e}", exc_info=True)
                
                # Log error evento
                log_system_event('error', details={
                    'error_type': 'runtime_error',
                    'error_message': str(e),
                    'thread_id': st.session_state.thread_id
                })
                
                st.error(
                    "Se produjo un error técnico. El equipo ha sido notificado. "
                    "Por favor, intenta reformular tu consulta."
                )
            
            # Mostrar respuesta
            if final_response_content:
                message_placeholder.markdown(final_response_content)
    
    # Guardar en historial
    if final_response_content:
        st.session_state.messages.append({
            "role": "assistant", 
            "content": final_response_content
        })

# ========================================
# FOOTER
# ========================================

st.divider()
st.caption("💡 Tip: Sé específico con tus consultas. Incluye todos los valores necesarios para los cálculos.")