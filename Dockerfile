FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias de sistema para compilar psycopg (Postgres)
RUN apt-get update && apt-get install -y build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Puerto por defecto de Cloud Run
ENV PORT=8080

# Iniciar la API con Uvicorn
CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT}"]