# api.py
import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

# IMPORTANTE: Importamos el grafo YA COMPILADO.
# Tu archivo 'graph/agent_graph.py' ya contiene la lógica para conectarse 
# automáticamente a PostgreSQL si la variable ENABLE_POSTGRES_PERSISTENCE es True.
from graph.agent_graph import compiled_graph

# Inicializar FastAPI
app = FastAPI(
    title="CFAAgent Backend",
    version="2.5.0",
    description="Microservicio de IA Financiera con Memoria Persistente (Cloud SQL)"
)

# --- MODELO DE DATOS ---
# Definimos exactamente qué esperamos recibir de Vercel
class ChatRequest(BaseModel):
    message: str       # El mensaje del usuario ("Calcula el VAN...")
    thread_id: str     # La identidad del usuario ("usuario@gmail.com")

# --- ENDPOINT DE SALUD ---
# Útil para que Cloud Run sepa que el servicio está vivo
@app.get("/")
@app.get("/health")
def health_check():
    return {"status": "online", "service": "CFAAgent Brain"}

# --- ENDPOINT PRINCIPAL (El Cerebro) ---
@app.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Recibe el mensaje y el ID de usuario.
    Orquesta la memoria (SQL), el razonamiento (Agentes) y la respuesta.
    """
    try:
        print(f"📩 Procesando mensaje para: {req.thread_id}")

        # 1. Configuración de Sesión (Memoria)
        # Al pasar 'thread_id', LangGraph buscará automáticamente en PostgreSQL
        # el historial de ESTE usuario específico antes de responder.
        config = {
            "configurable": {
                "thread_id": req.thread_id
            }
        }
        
        # 2. Ejecución del Grafo (Pensamiento + RAG + Cálculo)
        # Aquí ocurre toda la magia de tus agentes financieros
        final_state = compiled_graph.invoke(
            {"messages": [HumanMessage(content=req.message)]}, 
            config=config
        )
        
        # 3. Extracción de Respuesta
        # Obtenemos el último mensaje generado por la IA
        messages = final_state.get("messages", [])
        if not messages:
            raise HTTPException(status_code=500, detail="El agente no generó respuesta.")
            
        last_message = messages[-1]
        
        # Convertimos a texto limpio para enviar al frontend
        response_text = (
            last_message.content 
            if isinstance(last_message, AIMessage) 
            else str(last_message)
        )
        
        return {"response": response_text}

    except Exception as e:
        print(f"❌ Error crítico en chat_endpoint: {e}")
        # Devolvemos un error 500 explicativo si algo falla
        raise HTTPException(status_code=500, detail=str(e))

# Configuración para ejecución local (si ejecutas python api.py)
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)