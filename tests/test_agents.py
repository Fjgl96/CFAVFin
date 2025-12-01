"""
Tests para agentes especializados.
Valida que los agentes respondan correctamente con protocolos de señales.
"""

import pytest
from langchain_core.messages import HumanMessage, AIMessage


# ========================================
# FIXTURES
# ========================================

@pytest.fixture
def agent_fin_corp():
    """Fixture para Agente Finanzas Corporativas"""
    from agents.financial_agents import agent_fin_corp
    return agent_fin_corp


@pytest.fixture
def agent_portafolio():
    """Fixture para Agente Portafolio"""
    from agents.financial_agents import agent_portafolio
    return agent_portafolio


@pytest.fixture
def agent_renta_fija():
    """Fixture para Agente Renta Fija"""
    from agents.financial_agents import agent_renta_fija
    return agent_renta_fija


# ========================================
# TESTS AGENTE FINANZAS CORPORATIVAS
# ========================================

def test_agent_fin_corp_van_completo(agent_fin_corp):
    """Test VAN con todos los parámetros - debe retornar TAREA_COMPLETADA"""
    state = {
        "messages": [
            HumanMessage(content="Calcula VAN: inversión 100000, flujos [30000, 40000, 50000], tasa 10%")
        ]
    }

    result = agent_fin_corp.invoke(state)

    # Verificar que hay respuesta
    assert "messages" in result
    assert len(result["messages"]) > 0

    # Extraer último mensaje
    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Verificar señal de éxito
    assert "TAREA_COMPLETADA" in response, f"Respuesta: {response}"
    assert "VAN" in response or "van" in response.lower()


def test_agent_fin_corp_van_sin_parametros(agent_fin_corp):
    """Test VAN sin parámetros - debe retornar FALTAN_DATOS"""
    state = {
        "messages": [
            HumanMessage(content="Calcula el VAN")
        ]
    }

    result = agent_fin_corp.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Debe pedir datos faltantes
    assert "FALTAN_DATOS" in response, f"Respuesta: {response}"


def test_agent_fin_corp_fuera_especialidad(agent_fin_corp):
    """Test tarea fuera de especialidad - debe retornar FALTAN_DATOS"""
    state = {
        "messages": [
            HumanMessage(content="Calcula el valor de una opción call")
        ]
    }

    result = agent_fin_corp.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Debe rechazar por no ser su especialidad
    assert "No es mi especialidad" in response or "FALTAN_DATOS" in response


# ========================================
# TESTS AGENTE PORTAFOLIO
# ========================================

def test_agent_portafolio_capm_completo(agent_portafolio):
    """Test CAPM con todos los parámetros - debe calcular correctamente"""
    state = {
        "messages": [
            HumanMessage(content="Calcula CAPM: rf=3%, beta=1.2, rm=10%")
        ]
    }

    result = agent_portafolio.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Verificar señal de éxito
    assert "TAREA_COMPLETADA" in response, f"Respuesta: {response}"
    assert "Ke" in response or "costo equity" in response.lower()


def test_agent_portafolio_sharpe_sin_parametros(agent_portafolio):
    """Test Sharpe sin parámetros - debe pedir datos"""
    state = {
        "messages": [
            HumanMessage(content="Calcula el Sharpe Ratio")
        ]
    }

    result = agent_portafolio.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    assert "FALTAN_DATOS" in response


# ========================================
# TESTS AGENTE RENTA FIJA
# ========================================

def test_agent_renta_fija_bono_completo(agent_renta_fija):
    """Test valor bono con todos los parámetros"""
    state = {
        "messages": [
            HumanMessage(content="Calcula valor bono: nominal 1000, cupón 5%, YTM 6%, 10 años, frecuencia 2")
        ]
    }

    result = agent_renta_fija.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Verificar señal de éxito
    assert "TAREA_COMPLETADA" in response, f"Respuesta: {response}"


def test_agent_renta_fija_sin_parametros(agent_renta_fija):
    """Test sin parámetros - debe pedir datos"""
    state = {
        "messages": [
            HumanMessage(content="Calcula el valor de un bono")
        ]
    }

    result = agent_renta_fija.invoke(state)

    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    assert "FALTAN_DATOS" in response


# ========================================
# TESTS PROTOCOLO DE SEÑALES
# ========================================

def test_protocol_signals_consistency():
    """Test que todas las señales de protocolo están definidas correctamente"""
    from agents.financial_agents import (
        PROMPT_FIN_CORP, PROMPT_PORTAFOLIO, PROMPT_RENTA_FIJA,
        PROMPT_EQUITY, PROMPT_DERIVADOS
    )

    prompts = [
        PROMPT_FIN_CORP, PROMPT_PORTAFOLIO, PROMPT_RENTA_FIJA,
        PROMPT_EQUITY, PROMPT_DERIVADOS
    ]

    for prompt in prompts:
        # Verificar que contienen las señales clave
        assert "FALTAN_DATOS" in prompt
        assert "ERROR_BLOQUEANTE" in prompt
        assert "TAREA_COMPLETADA" in prompt
        assert "PROTOCOLO" in prompt
        assert "PASO" in prompt


# ========================================
# [NUEVO] TEST PROTOCOLO SEGURIDAD (NIVEL 2)
# ========================================

def test_agent_fin_corp_rechaza_teoria(agent_fin_corp):
    """
    Test de Protocolo de Seguridad:
    Valida que el agente RECHACE preguntas teóricas y emita la señal de transferencia.
    Esto actúa como red de seguridad si el router falla.
    """
    state = {
        "messages": [
            HumanMessage(content="¿Qué es el WACC y para qué sirve?")
        ]
    }

    result = agent_fin_corp.invoke(state)

    # Extraer respuesta
    last_message = result["messages"][-1]
    response = last_message.content if hasattr(last_message, 'content') else str(last_message)

    # Validación crítica: Debe contener la señal de transferencia
    assert "TRANSFERIR_A_RAG" in response, \
        f"El agente debió transferir a RAG, pero respondió: {response}"
    
    # Validación secundaria: No debe intentar calcular nada (sin tool calls)
    assert not getattr(last_message, 'tool_calls', []), \
        "El agente intentó usar herramientas en una pregunta teórica"


# ========================================
# RUNNER
# ========================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])