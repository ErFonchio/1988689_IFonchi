# Replica Backend - Flask SSE Proxy

Backend Flask che funge da proxy SSE per il simulatore di segnali sismici.

## Caratteristiche

- **SSE Proxy**: Connette a `localhost:8080/api/control` e espone gli stream SSE
- **Health Check**: Endpoint `/health` per verificare lo stato dell'applicazione
- **Status Endpoint**: Endpoint `/api/status` per controllare la connessione al simulatore upstream
- **Containerizzato**: Dockerfile per eseguire in Docker

## Setup Locale

### 1. Installa le dipendenze

```bash
pip install -r requirements.txt
```

### 2. Avvia l'applicazione

```bash
python app.py
```

L'app sarà disponibile su `http://0.0.0.0:5000`

## Setup Docker

### 1. Build dell'immagine

```bash
docker build -t seismic-replica:latest .
```

### 2. Esegui il container

```bash
docker run -p 5000:5000 seismic-replica:latest
```

Il container sarà disponibile su `http://0.0.0.0:5000`

### 3. Ferma il container

```bash
docker stop <container-id>
```

## Endpoint

### GET /api/control
Stream SSE proxy verso il simulatore.
```bash
curl -N http://localhost:5000/api/control
```

### GET /api/status
Verifica la connessione al simulatore upstream.
```bash
curl http://localhost:5000/api/status
```

### GET /health
Health check dell'applicazione.
```bash
curl http://localhost:5000/health
```

## Architettura

```
Client
  ↓
Flask App (porta 5000)
  ↓ (proxy SSE)
Simulatore (porta 8080)
```

## Note

- Il simulatore deve essere in esecuzione su `localhost:8080`
- La connessione SSE è mantenuta in un thread separato (`daemon=True`)
- I messaggi ricevuti dal simulatore sono accodati e trasmessi ai client
