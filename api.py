# api.py
import os
import uvicorn
from datetime import datetime
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

# api.py (Solo modifica la función get_history)

@app.get("/history")
async def get_history(
    thread_id: str = Query(..., description="La identidad del usuario (email)")
):
    """
    Recupera el historial filtrando mensajes intermedios del sistema.
    """
    try:
        config = {"configurable": {"thread_id": thread_id}}
        current_state = compiled_graph.get_state(config)
        
        if not current_state.values:
            return {"messages": []}
            
        raw_messages = current_state.values.get("messages", [])
        
        history = []
        for msg in raw_messages:
            # Determinar rol
            role = None
            if isinstance(msg, HumanMessage):
                role = "usuario"
            elif isinstance(msg, AIMessage):
                # Opcional: Filtrar mensajes vacíos (llamadas a tools sin texto)
                if not msg.content: 
                    continue
                role = "bot"
            
            if not role: 
                continue # Saltar ToolMessages o SystemMessages
                
            # --- FILTRO DE LIMPIEZA ---
            # Si es un mensaje de usuario y el ÚLTIMO mensaje guardado también fue de usuario,
            # ignoramos este nuevo. Esto oculta las "traducciones" internas del Supervisor
            # (ej: oculta "Bond definition" si ya tenemos "¿Qué es un bono?").
            if role == "usuario" and history and history[-1]["de"] == "usuario":
                continue
            # --------------------------

            fecha = msg.additional_kwargs.get("timestamp")

            history.append({
                "id": str(msg.id) if hasattr(msg, 'id') and msg.id else f"hist-{len(history)}", 
                "de": role,
                "texto": msg.content,
                "fecha": fecha
            })
            
        return {"messages": history}

    except Exception as e:
        print(f"❌ Error recuperando historial: {e}")
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


        timestamp_actual = datetime.now().isoformat()
        
        # Creamos el mensaje manualmente inyectando el timestamp en additional_kwargs
        # Esto asegura que LangGraph lo guarde en la base de datos con este dato.
        msg_usuario = HumanMessage(
            content=message, 
            additional_kwargs={"timestamp": timestamp_actual}
        )
        
        # 2. Ejecución del Grafo (Pensamiento + RAG + Cálculo)
        final_state = compiled_graph.invoke(
            {"messages": [msg_usuario]}, 
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