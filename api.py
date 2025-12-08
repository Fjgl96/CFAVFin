# api.py
"""
CFAAgent Backend API
- Paginación optimizada para historial
- Soporte para usuarios autenticados e invitados
"""

import os
import uvicorn
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, AIMessage
from fastapi.responses import StreamingResponse # <--- IMPORTANTE
import json

# IMPORTANTE: Importamos el grafo YA COMPILADO.
from graph.agent_graph import compiled_graph

# Inicializar FastAPI
app = FastAPI(
    title="CFAAgent Backend",
    version="2.6.0",
    description="Microservicio de IA Financiera con Memoria Persistente y Paginación"
)

# CORS para permitir requests del frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINT DE SALUD ---
@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "online", "service": "CFAAgent Brain", "version": "2.6.0"}


# --- ENDPOINT DE HISTORIAL CON PAGINACIÓN ---
@app.get("/history")
async def get_history(
    thread_id: str = Query(..., description="La identidad del usuario (email o guest_id)"),
    limit: int = Query(50, ge=1, le=200, description="Máximo de mensajes a devolver"),
    offset: int = Query(0, ge=0, description="Número de mensajes a saltar (para paginación)")
):
    """
    Recupera el historial con paginación.
    
    - Los mensajes se devuelven en orden cronológico inverso (más recientes primero)
    - `limit`: máximo de mensajes por página (default 50, max 200)
    - `offset`: cuántos mensajes saltar desde los más recientes (default 0)
    
    Respuesta:
    - messages: lista de mensajes
    - hasMore: boolean indicando si hay más mensajes antiguos
    - total: número total de mensajes disponibles
    """
    try:
        # Verificar si es un usuario invitado (no cargar historial)
        if thread_id.startswith("guest_"):
            return {
                "messages": [],
                "hasMore": False,
                "total": 0,
                "isGuest": True
            }
        
        config = {"configurable": {"thread_id": thread_id}}
        current_state = compiled_graph.get_state(config)
        
        if not current_state.values:
            return {"messages": [], "hasMore": False, "total": 0}
            
        raw_messages = current_state.values.get("messages", [])
        
        # Filtrar y procesar mensajes
        history = []
        for msg in raw_messages:
            role = None
            if isinstance(msg, HumanMessage):
                role = "usuario"
            elif isinstance(msg, AIMessage):
                # Filtrar mensajes vacíos (llamadas a tools sin texto)
                if not msg.content: 
                    continue
                role = "bot"
            
            if not role: 
                continue  # Saltar ToolMessages o SystemMessages
                
            # --- FILTRO DE LIMPIEZA ---
            # Si es un mensaje de usuario y el ÚLTIMO mensaje guardado también fue de usuario,
            # ignoramos este nuevo. Esto oculta las "traducciones" internas del Supervisor.
            if role == "usuario" and history and history[-1]["de"] == "usuario":
                continue

            fecha = msg.additional_kwargs.get("timestamp")

            history.append({
                "id": str(msg.id) if hasattr(msg, 'id') and msg.id else f"hist-{len(history)}", 
                "de": role,
                "texto": msg.content,
                "fecha": fecha
            })
        
        # IMPORTANTE: Invertir para que los más recientes estén primero
        history.reverse()
        
        # PAGINACIÓN
        total_messages = len(history)
        paginated = history[offset : offset + limit]
        has_more = (offset + limit) < total_messages
        
        return {
            "messages": paginated,
            "hasMore": has_more,
            "total": total_messages
        }

    except Exception as e:
        print(f"❌ Error recuperando historial: {e}")
        return {"messages": [], "hasMore": False, "total": 0}


# --- ENDPOINT PRINCIPAL DE CHAT ---
@app.get("/chat")
async def chat_endpoint(
    message: str = Query(..., description="El mensaje del usuario"), 
    thread_id: str = Query(..., description="La identidad del usuario")
):
    try:
        # Configuración
        config = {"configurable": {"thread_id": thread_id}}
        timestamp_actual = datetime.now().isoformat()
        msg_usuario = HumanMessage(content=message, additional_kwargs={"timestamp": timestamp_actual})

        # Generador de eventos para el streaming
        async def event_stream():
            # astream_events captura eventos internos del grafo
            async for event in compiled_graph.astream_events(
                {"messages": [msg_usuario]}, 
                config=config,
                version="v1"
            ):
                # Filtramos SOLO los tokens de texto generados por los modelos de chat
                kind = event["event"]
                
                # 'on_chat_model_stream' es el evento cuando el LLM genera un token
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    if hasattr(chunk, "content") and chunk.content:
                        # Enviamos solo el texto
                        yield chunk.content

        # Retornamos el stream directo
        return StreamingResponse(event_stream(), media_type="text/plain")

    except Exception as e:
        print(f"❌ Error chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- ENDPOINT PARA VERIFICAR ESTADO DE SESIÓN ---
@app.get("/session/status")
async def session_status(thread_id: str = Query(..., description="ID del usuario")):
    """
    Verifica el estado de la sesión de un usuario.
    Útil para el frontend para saber si el usuario tiene historial.
    """
    try:
        is_guest = thread_id.startswith("guest_")
        
        if is_guest:
            return {
                "isGuest": True,
                "hasHistory": False,
                "messageCount": 0
            }
        
        config = {"configurable": {"thread_id": thread_id}}
        current_state = compiled_graph.get_state(config)
        
        if not current_state.values:
            return {
                "isGuest": False,
                "hasHistory": False,
                "messageCount": 0
            }
        
        raw_messages = current_state.values.get("messages", [])
        message_count = len([m for m in raw_messages if isinstance(m, (HumanMessage, AIMessage)) and (not isinstance(m, AIMessage) or m.content)])
        
        return {
            "isGuest": False,
            "hasHistory": message_count > 0,
            "messageCount": message_count
        }
        
    except Exception as e:
        print(f"❌ Error verificando sesión: {e}")
        return {
            "isGuest": thread_id.startswith("guest_"),
            "hasHistory": False,
            "messageCount": 0
        }


# Configuración para ejecución local
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)