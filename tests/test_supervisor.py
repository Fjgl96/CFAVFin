"""
Tests para el supervisor y circuit breaker.
Valida la lógica de enrutamiento y prevención de bucles.
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage


# ========================================
# TESTS DETECCIÓN DE SEÑALES
# ========================================

def test_detect_tarea_completada():
    """Test detección de señal TAREA_COMPLETADA"""
    from graph.agent_graph import detect_error_type

    message = AIMessage(content="El VAN es $2,892. Interpretación: Rentable. TAREA_COMPLETADA")

    result = detect_error_type(message)

    assert result == 'success', f"Se esperaba 'success', obtuvo '{result}'"


def test_detect_faltan_datos():
    """Test detección de señal FALTAN_DATOS"""
    from graph.agent_graph import detect_error_type

    message = AIMessage(content="FALTAN_DATOS: Necesito inversión_inicial y tasa_descuento.")

    result = detect_error_type(message)

    assert result == 'validation', f"Se esperaba 'validation', obtuvo '{result}'"


def test_detect_error_bloqueante():
    """Test detección de señal ERROR_BLOQUEANTE"""
    from graph.agent_graph import detect_error_type

    message = AIMessage(content="ERROR_BLOQUEANTE: La inversión debe ser mayor que 0.")

    result = detect_error_type(message)

    # ERROR_BLOQUEANTE podría clasificarse como tool_failure o validation
    assert result in ['tool_failure', 'validation', 'capability']


def test_detect_no_es_especialidad():
    """Test detección de mensaje de 'no es mi especialidad'"""
    from graph.agent_graph import detect_error_type

    message = AIMessage(content="No es mi especialidad. FALTAN_DATOS: Requiere otro agente.")

    result = detect_error_type(message)

    # Podría ser capability o validation
    assert result in ['capability', 'validation']


# ========================================
# TESTS CIRCUIT BREAKER
# ========================================

def test_circuit_breaker_logic():
    """Test lógica del circuit breaker"""
    from graph.agent_graph import should_open_circuit

    # Caso 1: Muchos fallos de herramientas
    error_types = {'tool_failure': 2}
    error_count = 2

    assert should_open_circuit(error_types, error_count) is True

    # Caso 2: Muchos errores de validación
    error_types = {'validation': 3}
    error_count = 3

    assert should_open_circuit(error_types, error_count) is True

    # Caso 3: Pocos errores - no debe activarse
    error_types = {'validation': 1}
    error_count = 1

    assert should_open_circuit(error_types, error_count) is False


# ========================================
# TESTS SUPERVISOR NODE
# ========================================

def test_supervisor_node_handles_tarea_completada():
    """Test que supervisor detecta TAREA_COMPLETADA y responde FINISH"""
    from graph.agent_graph import supervisor_node

    state = {
        "messages": [
            HumanMessage(content="Calcula VAN"),
            AIMessage(content="El VAN es $2,892. TAREA_COMPLETADA")
        ],
        "error_count": 0,
        "error_types": {},
        "circuit_open": False
    }

    result = supervisor_node(state)

    # Debe retornar FINISH
    assert result["next_node"] == "FINISH", f"Se esperaba FINISH, obtuvo {result['next_node']}"


def test_supervisor_node_handles_faltan_datos():
    """Test que supervisor detecta FALTAN_DATOS y responde FINISH"""
    from graph.agent_graph import supervisor_node

    state = {
        "messages": [
            HumanMessage(content="Calcula VAN"),
            AIMessage(content="FALTAN_DATOS: Necesito inversión_inicial. Por favor proporciona estos valores.")
        ],
        "error_count": 0,
        "error_types": {},
        "circuit_open": False
    }

    result = supervisor_node(state)

    # Debe retornar FINISH
    assert result["next_node"] == "FINISH"


def test_supervisor_node_circuit_breaker_activated():
    """Test que supervisor respeta circuit breaker activado"""
    from graph.agent_graph import supervisor_node

    state = {
        "messages": [
            HumanMessage(content="Test query")
        ],
        "error_count": 5,
        "error_types": {'validation': 3},
        "circuit_open": True  # Ya activado
    }

    result = supervisor_node(state)

    # Debe retornar FINISH inmediatamente
    assert result["next_node"] == "FINISH"
    assert result["circuit_open"] is True


def test_supervisor_node_new_query():
    """Test que supervisor enruta nueva pregunta del usuario"""
    from graph.agent_graph import supervisor_node

    state = {
        "messages": [
            HumanMessage(content="Calcula VAN: inversión 100k, flujos [30k, 40k], tasa 10%")
        ],
        "error_count": 0,
        "error_types": {},
        "circuit_open": False
    }

    result = supervisor_node(state)

    # Debe enrutar a un agente (no FINISH)
    assert result["next_node"] != "FINISH"
    assert result["next_node"] in [
        "Agente_Finanzas_Corp", "Agente_Portafolio", "Agente_Renta_Fija",
        "Agente_Equity", "Agente_Derivados", "Agente_RAG", "Agente_Ayuda"
    ]


# ========================================
# TESTS ESTADO DEL GRAFO
# ========================================

def test_graph_state_schema():
    """Test que el esquema de estado tiene los campos requeridos"""
    from graph.agent_graph import AgentState

    # Verificar que AgentState tiene los campos esperados
    assert 'messages' in AgentState.__annotations__
    assert 'next_node' in AgentState.__annotations__
    assert 'error_count' in AgentState.__annotations__
    assert 'error_types' in AgentState.__annotations__
    assert 'circuit_open' in AgentState.__annotations__


# ========================================
# TESTS INTEGRACIÓN GRAFO
# ========================================

def test_graph_can_be_compiled():
    """Test que el grafo se compila correctamente"""
    from graph.agent_graph import compiled_graph

    assert compiled_graph is not None
    assert hasattr(compiled_graph, 'invoke')


def test_graph_invoke_simple_query():
    """Test ejecución simple del grafo"""
    from graph.agent_graph import compiled_graph
    import uuid

    state = {
        "messages": [HumanMessage(content="Ayuda")]
    }
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # Ejecutar grafo
    result = compiled_graph.invoke(state, config=config)

    # Verificar que se ejecutó
    assert "messages" in result
    assert len(result["messages"]) > 0


# ========================================
# [NUEVO] TEST MANEJO DE SEÑALES DE TRANSFERENCIA (NIVEL 3)
# ========================================

def test_supervisor_handle_transfer_signal():
    """
    Test de Manejo de Señales:
    Valida que el supervisor reconozca 'TRANSFERIR_A_RAG' y redirija correctamente.
    Esto asegura que no haya bucles si el agente especialista rechaza la tarea.
    """
    from graph.agent_graph import supervisor_node
    
    # Simular estado donde el Agente especialista pide ayuda a RAG
    state = {
        "messages": [
            HumanMessage(content="¿Qué es el WACC?"),
            AIMessage(content="Esta es una consulta teórica. TRANSFERIR_A_RAG")
        ],
        "error_count": 0,
        "error_types": {},
        "circuit_open": False
    }

    result = supervisor_node(state)

    # El supervisor debe decidir ir al Agente_RAG
    assert result["next_node"] == "Agente_RAG", \
        f"Se esperaba 'Agente_RAG', obtuvo '{result['next_node']}'"


# ========================================
# RUNNER
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])