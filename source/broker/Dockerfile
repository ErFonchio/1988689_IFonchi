FROM python:3.11-slim

WORKDIR /app

# Installa le dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia l'applicazione
COPY custom_broker.py .

# Espone la porta
EXPOSE 5000

# Avvia l'app
CMD ["python", "custom_broker.py"]
