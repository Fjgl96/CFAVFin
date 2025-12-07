# api.py
import os
import uvicorn
from fastapi import FastAPI, HTTPException, Query # <--- Importamos Query
from langchain_core.messages import HumanMessage, AIMessage

# IMPORTANTE: Importamos el grafo YA COMPILADO.
from graph.agent_graph import compiled_graph

# Inicializar FastAPI
app = FastAPI(
    title="CFAAgent Backend",
    version="2.5.0",
    description="Microservicio de IA Financiera con Memoria Persistente (Cloud SQL)"
)

# --- ENDPOINT DE SALUD ---
@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "online", "service": "CFAAgent Brain"}

# --- NUEVO ENDPOINT: HISTORIAL ---
@app.get("/history")
async def get_history(
    thread_id: str = Query(..., description="La identidad del usuario (email)")
):
    """
    Recupera el historial de mensajes guardado en la persistencia (Postgres/Memory)
    para un usuario específico.
    """
    try:
        print(f"📂 Recuperando historial para: {thread_id}")
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Obtener el estado actual del grafo
        current_state = compiled_graph.get_state(config)
        
        # Si no hay estado (usuario nuevo), devolver lista vacía
        if not current_state.values:
            return {"messages": []}
            
        messages = current_state.values.get("messages", [])
        
        # Formatear para el frontend
        history = []
        for msg in messages:
            # Ignorar mensajes del sistema o de herramientas si solo queremos chat
            # Aunque LangGraph suele guardar Human y AI messages principalmente en la lista 'messages'
            role = "bot"
            if isinstance(msg, HumanMessage):
                role = "usuario"
            elif isinstance(msg, AIMessage):
                role = "bot"
            else:
                continue # Opcional: saltar mensajes que no sean chat
                
            history.append({
                "id": str(msg.id) if hasattr(msg, 'id') and msg.id else f"hist-{len(history)}", 
                "de": role,
                "texto": msg.content
            })
            
        return {"messages": history}

    except Exception as e:
        print(f"❌ Error recuperando historial: {e}")
        # No bloqueamos el frontend si falla el historial, devolvemos vacío
        return {"messages": []}


# --- ENDPOINT PRINCIPAL (MODIFICADO A GET) ---
@app.get("/chat")
async def chat_endpoint(
    message: str = Query(..., description="El mensaje del usuario"), 
    thread_id: str = Query(..., description="La identidad del usuario (email)")
):
    """
    Recibe el mensaje y el ID de usuario como parámetros de URL.
    Ejemplo: /chat?message=Hola&thread_id=juan@gmail.com
    """
    try:
        print(f"📩 Procesando mensaje GET para: {thread_id}")

        # 1. Configuración de Sesión (Memoria)
        config = {
            "configurable": {
                "thread_id": thread_id # Usamos la variable directa del Query param
            }
        }
        
        # 2. Ejecución del Grafo (Pensamiento + RAG + Cálculo)
        final_state = compiled_graph.invoke(
            {"messages": [HumanMessage(content=message)]}, # Usamos la variable directa
            config=config
        )
        
        # 3. Extracción de Respuesta
        messages = final_state.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="El agente no generó respuesta.")
            
        last_message = messages[-1]
        
        # Convertimos a texto limpio
        response_text = (
            last_message.content 
            if isinstance(last_message, AIMessage) 
            else str(last_message)
        )
        
        return {"response": response_text}

    except Exception as e:
        print(f"❌ Error crítico en chat_endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Configuración para ejecución local
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)