from flask import Flask, Response, jsonify
import requests
import threading
import logging
import os
from queue import Queue
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Usa 'simulator' come hostname in docker-compose, localhost per sviluppo locale
SIMULATOR_HOST = os.getenv('SIMULATOR_HOST', 'localhost')
UPSTREAM_URL = f"http://{SIMULATOR_HOST}:8080/api/control"

# Coda per bufferizzare i dati SSE
sse_queue = Queue(maxsize=100)
stream_thread = None
stream_connected = False


def connect_to_upstream():
    """Thread che rimane connesso al flusso SSE del simulatore"""
    global stream_connected
    
    while True:
        try:
            logger.info(f"Connessione a {UPSTREAM_URL}")
            # timeout=(connect_timeout, read_timeout)
            # read_timeout=None = aspetta indefinitamente i dati
            response = requests.get(UPSTREAM_URL, stream=True, timeout=(5, None))
            response.raise_for_status()
            
            logger.info("Connessione stabilita con il simulatore")
            stream_connected = True
            
            for line in response.iter_lines():
                if line:
                    line_str = line.decode('utf-8') if isinstance(line, bytes) else line
                    logger.info(f"Ricevuto dal simulatore: {line_str}")
                    # Formato SSE corretto
                    sse_queue.put(f"data: {line_str}\n\n")
                else:
                    # Heartbeat (linea vuota)
                    logger.debug("Heartbeat ricevuto dal simulatore")
                    sse_queue.put(":\n\n")  # Commento/heartbeat SSE
                    
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Errore connessione: {e}")
            stream_connected = False
            sse_queue.put(f"data: {{'error': 'Connection failed: {str(e)}'}}\n\n")
            time.sleep(5)  # Riprova dopo 5 secondi
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout: {e}")
            stream_connected = False
            sse_queue.put(f"data: {{'error': 'Timeout: {str(e)}'}}\n\n")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"Errore: {e}")
            stream_connected = False
            sse_queue.put(f"data: {{'error': '{str(e)}'}}\n\n")
            time.sleep(5)


def get_stream_from_queue():
    """Generator che legge dalla coda e trasmette ai client"""
    while True:
        try:
            data = sse_queue.get(timeout=30)
            yield data
        except:
            # Timeout dalla coda - invia heartbeat
            yield ":\n\n"


@app.route('/api/control', methods=['GET'])
def control_stream():
    """Proxy SSE: trasmette dai client il flusso del simulatore"""
    return Response(
        get_stream_from_queue(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/status', methods=['GET'])
def status():
    """Verifica connessione al simulatore"""
    try:
        response = requests.get(f"http://{SIMULATOR_HOST}:8080/api/status", timeout=2)
        return jsonify({'status': 'connected', 'upstream': response.status_code == 200})
    except:
        return jsonify({'status': 'disconnected', 'upstream': False}), 503


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({'status': 'healthy'}), 200


if __name__ == '__main__':
    logger.info("Starting Flask app on 0.0.0.0:5000")
    
    # Avvia il thread che rimane connesso al simulatore
    stream_thread = threading.Thread(target=connect_to_upstream, daemon=True)
    stream_thread.start()
    logger.info("Thread di streaming SSE avviato")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
