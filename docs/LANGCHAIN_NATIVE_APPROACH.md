# 🎓 Enfoque LangChain-Native: Routing con Runnables

## 📋 Por Qué Este Cambio es Importante

**Situación Original**: Implementé un sistema de routing usando clases Python vanilla (IRouter, FastPatternRouter, etc.) siguiendo patrones generales de arquitectura de software.

**Problema**: Este enfoque **no aprovecha las herramientas de LangChain** que ya están usando en el proyecto y que probablemente están aprendiendo en su curso.

**Solución**: Refactorizar usando **abstracciones nativas de LangChain** (Runnables, LCEL, RunnableBranch).

---

## ⚖️ Comparación: Dos Enfoques

### ❌ Enfoque Original (Clases Custom)

```python
# routing/interfaces.py
class IRouter(ABC):
    @abstractmethod
    def route(self, state) -> RoutingDecision:
        pass

# routing/fast_router.py
class FastPatternRouter(IRouter):
    def __init__(self, config_path):
        self.patterns = load_patterns(config_path)

    def route(self, state):
        # Lógica de pattern matching
        return RoutingDecision(...)

# routing/hybrid_router.py
class HybridRouter(IRouter):
    def __init__(self, fast_router, llm_router, threshold):
        self.fast = fast_router
        self.llm = llm_router
        self.threshold = threshold

    def route(self, state):
        fast_decision = self.fast.route(state)
        if fast_decision.confidence >= self.threshold:
            return fast_decision
        else:
            return self.llm.route(state)
```

**Problemas**:
- ❌ No usa abstracciones de LangChain
- ❌ No es composable con LCEL
- ❌ No aprovecha Runnables existentes
- ❌ Sistema paralelo al framework
- ❌ No es pedagógico para un curso de LangChain

---

### ✅ Enfoque LangChain-Native (Runnables)

```python
# routing/langchain_routing.py

from langchain_core.runnables import RunnableLambda, RunnableBranch

# 1. Lógica como función pura
def analyze_query_fast_pattern(state, patterns):
    """Función pura - fácil de testear."""
    # Pattern matching logic
    return {
        'target_agent': 'Agente_X',
        'confidence': 0.9,
        'metadata': {...}
    }

# 2. Convertir a Runnable
fast_pattern = RunnableLambda(
    lambda state: analyze_query_fast_pattern(state, patterns),
    name="fast_pattern_router"
)

# 3. Routing condicional con RunnableBranch
hybrid_routing = RunnableBranch(
    # (condición, runnable_si_verdadero)
    (lambda state: fast_pattern.invoke(state)['confidence'] >= 0.8,
     RunnableLambda(extract_fast_decision)),
    # default: runnable_si_falso
    RunnableLambda(use_supervisor_llm)
)

# 4. Uso en LangGraph (100% compatible)
def routing_node(state):
    next_agent = hybrid_routing.invoke(state)
    return {'next_node': next_agent}
```

**Ventajas**:
- ✅ Usa abstracciones de LangChain (RunnableLambda, RunnableBranch)
- ✅ Compatible con LCEL
- ✅ Composable con otras Runnables
- ✅ Integrado con el framework (no paralelo)
- ✅ Pedagógico - muestra mejores prácticas de LangChain

---

## 🧩 Conceptos Clave de LangChain

### 1. **Runnable** (Interfaz Base)

Todo en LangChain es un Runnable:
```python
# Todos estos son Runnables
llm = ChatAnthropic(...)          # ← Runnable
tool = @tool                       # ← Runnable (con decorator)
chain = llm | parser               # ← Runnable (LCEL)
lambda_fn = RunnableLambda(...)    # ← Runnable

# API común:
result = runnable.invoke(input)    # Ejecutar
async_result = await runnable.ainvoke(input)  # Async
for chunk in runnable.stream(input):  # Streaming
```

### 2. **RunnableLambda** (Wrappear Funciones)

Convierte cualquier función en Runnable:
```python
def my_function(state):
    return {"result": "processed"}

# Convertir a Runnable
my_runnable = RunnableLambda(my_function, name="my_step")

# Ahora es composable con LCEL
chain = my_runnable | another_runnable
```

### 3. **RunnableBranch** (Routing Condicional)

Patrón idiomático para decisiones condicionales:
```python
routing = RunnableBranch(
    # (condición, runnable_si_verdadero)
    (lambda x: x["score"] > 0.8, high_confidence_path),
    (lambda x: x["score"] > 0.5, medium_confidence_path),
    # default (sin condición)
    low_confidence_path
)

# Uso
result = routing.invoke({"score": 0.9})  # → high_confidence_path
```

### 4. **LCEL** (LangChain Expression Language)

Composición de Runnables usando `|`:
```python
# Composición secuencial
chain = step1 | step2 | step3

# Equivalente a:
result = step3.invoke(step2.invoke(step1.invoke(input)))

# Con routing condicional
chain = (
    RunnableLambda(extract_query)
    | RunnableBranch(
        (is_calculation, fast_router),
        supervisor_llm
    )
    | RunnableLambda(format_output)
)
```

---

## 📊 Comparación de Arquitectura

### Enfoque Original (Clases Custom)

```
Usuario Query
    ↓
HybridRouter (clase custom)
    ├─ FastPatternRouter.route() → RoutingDecision
    └─ LLMRouter.route() → RoutingDecision
    ↓
Extraer target_agent de RoutingDecision
    ↓
Agente
```

**Problema**: Sistema paralelo, no integrado con LangChain.

---

### Enfoque LangChain-Native

```
Usuario Query
    ↓
RunnableBranch (nativo de LangChain)
    ├─ Condición: confidence >= 0.8
    │   ├─ TRUE: RunnableLambda(fast_pattern) → target_agent
    │   └─ FALSE: RunnableLambda(supervisor_llm) → target_agent
    ↓
Agente
```

**Ventaja**: 100% nativo de LangChain, composable, extensible.

---

## 🔧 Ejemplo Práctico: Cómo Funciona

### Caso 1: Bypass con Fast Pattern

```python
state = {
    "messages": [HumanMessage(content="Calcula VAN: 100k, [30k, 40k], 10%")]
}

# RunnableBranch evalúa condición
condition_result = should_use_fast_pattern(state)
# → True (confidence >= 0.8)

# Ejecuta rama TRUE
target = extract_fast_decision(state)
# → "Agente_Finanzas_Corp"

# Resultado
{'next_node': 'Agente_Finanzas_Corp', 'method': 'fast_pattern', ...}
```

### Caso 2: Fallback a LLM

```python
state = {
    "messages": [HumanMessage(content="¿Qué es el VAN?")]
}

# RunnableBranch evalúa condición
condition_result = should_use_fast_pattern(state)
# → False (confidence < 0.8)

# Ejecuta rama DEFAULT (LLM)
target = use_supervisor_llm(state)
# → supervisor_llm.invoke([prompt] + messages)
# → "Agente_RAG"

# Resultado
{'next_node': 'Agente_RAG', 'method': 'llm', ...}
```

---

## 🎯 Ventajas del Enfoque LangChain-Native

### 1. **Pedagógico**

Si están en un curso de LangChain, este código:
- ✅ Muestra cómo usar RunnableBranch correctamente
- ✅ Demuestra composición con LCEL
- ✅ Sigue las mejores prácticas del framework
- ✅ Es reutilizable en otros proyectos LangChain

### 2. **Mantenible**

```python
# Fácil de extender sin modificar código
new_routing = (
    fast_pattern
    | RunnableBranch(
        (is_ambiguous, clarification_agent),
        (is_calculation, calculator_agent),
        default_agent
    )
)
```

### 3. **Testable**

```python
# Funciones puras son fáciles de testear
def test_fast_pattern():
    state = {"messages": [HumanMessage(content="test")]}
    patterns = {...}

    result = analyze_query_fast_pattern(state, patterns)

    assert result['target_agent'] == 'Expected'
    assert result['confidence'] >= 0.8
```

### 4. **Composable**

```python
# Se puede integrar en cadenas LCEL más grandes
full_chain = (
    input_parser
    | routing_branch       # ← Nuestro routing
    | agent_executor
    | output_formatter
)
```

---

## 📚 Recursos de LangChain Relacionados

### Documentación Oficial

1. **Runnables**: https://python.langchain.com/docs/concepts/runnables
2. **LCEL**: https://python.langchain.com/docs/concepts/lcel
3. **RunnableBranch**: https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.branch.RunnableBranch.html
4. **RunnableLambda**: https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.base.RunnableLambda.html

### Ejemplos en el Proyecto

```python
# Ya están usando Runnables en varios lugares:

# 1. LLM con fallback (config.py:230)
llm_with_fallback = llm_primary.with_fallbacks([llm_fallback])

# 2. LLM con system prompt (agents/financial_agents.py:209)
llm_with_system = llm.bind(system=system_prompt)

# 3. Structured output (agents/financial_agents.py:528)
supervisor_llm = llm.with_structured_output(RouterSchema)

# 4. Tools como Runnables (tools/financial_tools.py)
@tool
def _calcular_van(...):
    # Esta función es automáticamente un Runnable
```

---

## 🔄 Migración: Qué Cambió

### Archivos Antiguos (Deprecados)

Estos archivos están en `routing/` pero **NO se usan más**:
- ❌ `routing/interfaces.py` (IRouter, RoutingDecision como dataclass)
- ❌ `routing/fast_router.py` (FastPatternRouter como clase)
- ❌ `routing/llm_router.py` (LLMRouter como clase)
- ❌ `routing/hybrid_router.py` (HybridRouter como clase)
- ❌ `routing/orchestrator.py` (RouterOrchestrator como clase)

**Nota**: Estos archivos se mantienen para referencia, pero NO se usan en el sistema.

### Archivo Nuevo (En Uso)

- ✅ `routing/langchain_routing.py` - **Versión LangChain-native**
  - Usa `RunnableLambda`
  - Usa `RunnableBranch`
  - Compatible con LCEL
  - Funciones puras + Runnables

### Cambios en `graph/agent_graph.py`

```diff
- from routing import FastPatternRouter, LLMRouter, HybridRouter
+ from routing.langchain_routing import create_routing_node

- ROUTING_SYSTEM = HybridRouter(...)
+ ROUTING_NODE = create_routing_node(...)

- decision = ROUTING_SYSTEM.route(state)
+ result = ROUTING_NODE(state)
```

---

## ✅ Conclusión

### Por Qué Este Cambio es Correcto

1. **Alineado con LangChain**: Usa abstracciones del framework
2. **Pedagógico**: Muestra mejores prácticas del curso
3. **Mantenible**: Más fácil de extender y modificar
4. **Composable**: Se integra con LCEL
5. **Idiomático**: Sigue los patrones de LangChain/LangGraph

### Qué Conservamos

- ✅ Misma lógica de pattern matching
- ✅ Mismo archivo YAML de configuración
- ✅ Misma funcionalidad de routing híbrido
- ✅ Misma mejora de rendimiento (~50%)
- ✅ Mismas garantías de estabilidad

### Qué Mejoramos

- ✅ Usa Runnables en vez de clases custom
- ✅ Composable con LCEL
- ✅ Más fácil de testear (funciones puras)
- ✅ Alineado con el framework
- ✅ Código más claro y conciso

---

**Recomendación**: Si estás en un curso de LangChain, usa la versión LangChain-native (`langchain_routing.py`). Es el enfoque correcto y te ayudará a entender mejor el framework.
