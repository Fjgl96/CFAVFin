#!/usr/bin/env python3
"""
Script de validación del nuevo sistema de routing simplificado.
Prueba los 3 casos: TEORICA, PRACTICA, AYUDA
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from langchain_core.messages import HumanMessage
from graph.agent_graph import supervisor_node, AgentState

print("🧪 VALIDACIÓN DE ROUTING SIMPLIFICADO")
print("=" * 60)

# Casos de prueba
test_cases = [
    {
        "name": "CASO 1: Teoría",
        "query": "¿Qué es el WACC?",
        "expected_node": "Agente_RAG",
        "expected_method": "clasificacion_llm"
    },
    {
        "name": "CASO 2: Práctica",
        "query": "Calcula VAN: inversión 100k, flujos [30k,40k], tasa 10%",
        "expected_node": "Agente_Finanzas_Corp",
        "expected_method": "clasificacion_practica"
    },
    {
        "name": "CASO 3: Ayuda",
        "query": "¿Qué puedes hacer?",
        "expected_node": "Agente_Ayuda",
        "expected_method": "clasificacion_llm"
    }
]

results = []

for i, test in enumerate(test_cases, 1):
    print(f"\n{test['name']}")
    print("-" * 60)
    print(f"Query: {test['query']}")

    # Crear estado inicial
    state: AgentState = {
        "messages": [HumanMessage(content=test['query'])],
        "next_node": "",
        "error_count": 0,
        "error_types": {},
        "last_error_time": 0.0,
        "circuit_open": False
    }

    try:
        # Ejecutar supervisor
        result = supervisor_node(state)

        next_node = result.get("next_node")
        routing_method = result.get("routing_method")
        confidence = result.get("routing_confidence", 0.0)

        # Validar resultado
        node_ok = next_node == test['expected_node']
        method_ok = routing_method == test['expected_method']

        status = "✅ PASS" if (node_ok and method_ok) else "❌ FAIL"
        results.append(node_ok and method_ok)

        print(f"Resultado: {next_node} (método: {routing_method}, conf: {confidence:.2f})")
        print(f"Esperado: {test['expected_node']} (método: {test['expected_method']})")
        print(f"Status: {status}")

        if not node_ok:
            print(f"⚠️ Nodo incorrecto: esperado {test['expected_node']}, obtuvo {next_node}")
        if not method_ok:
            print(f"⚠️ Método incorrecto: esperado {test['expected_method']}, obtuvo {routing_method}")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

# Resumen final
print("\n" + "=" * 60)
print("📊 RESUMEN DE VALIDACIÓN")
print("=" * 60)
passed = sum(results)
total = len(results)
print(f"Tests pasados: {passed}/{total}")

if passed == total:
    print("✅ TODOS LOS TESTS PASARON")
    print("\n🎉 Sistema de routing simplificado funcionando correctamente")
    sys.exit(0)
else:
    print(f"❌ {total - passed} TEST(S) FALLARON")
    print("\n⚠️ Revisa los errores arriba")
    sys.exit(1)
