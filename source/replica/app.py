from flask import Flask, Response, jsonify
import requests
import threading
import logging
import os
import json
import sys
import socket
from queue import Queue
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Usa 'simulator' come hostname in docker-compose, localhost per sviluppo locale
SIMULATOR_HOST = os.getenv('SIMULATOR_HOST', 'localhost')
UPSTREAM_URL = f"http://{SIMULATOR_HOST}:8080/api/control"

# Configurazione connessione al broker
BROKER_HOST = os.getenv('BROKER_HOST', 'localhost')
BROKER_PORT = int(os.getenv('BROKER_PORT', 5001))

# Coda per bufferizzare i dati SSE
sse_queue = Queue(maxsize=100)
stream_thread = None
stream_connected = False

# ACK constant per broker communication
ACK = b"ACK"
LEADER = b"LEADER"

class SlaveClient:
    """Client slave che si connette al broker master"""
    def __init__(self, master_host: str, master_port: int, max_retries: int = 10):
        self.sock = None
        self.max_retries = max_retries
        self.leader = False
        self._connect(master_host, master_port)

        ## Just for printing
        self.count = 0
    
    def _connect(self, master_host: str, master_port: int):
        """Prova a connettersi con retry"""
        logger.info(f"Tentativo di connessione al broker {master_host}:{master_port}")
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Tentativo {attempt + 1}/{self.max_retries}: Connessione a {master_host}:{master_port}")
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((master_host, master_port))
                logger.info(f"✓ SlaveClient CONNESSO a {master_host}:{master_port}")

                return
            except Exception as e:
                logger.warning(f"Tentativo {attempt + 1}/{self.max_retries} fallito: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
        
        raise Exception(f"Impossibile connettersi a {master_host}:{master_port} dopo {self.max_retries} tentativi")


    def run(self):
        # get data from broker, and send ack
        while True:
            data = self.sock.recv(4096)

            if not data:
                break 

            # Check if the master is electing me as leader
            if data == LEADER:
                self.leader = True
            else:
                # read measurements
                measures = json.loads(data.decode())

                if self.count % 20 == 0:
                    logger.info(f"Received data: {measures}")

            self.count += 1
            # send ACK 
            self.sock.sendall(ACK)
        try:
            if self.sock:
                self.sock.close()
        except:
            pass



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
                    
                    # Controlla se è uno shutdown command
                    try:
                        if 'shutdown' in line_str.lower():
                            logger.warning("⚠️ Shutdown rilevato (stringa)! Chiusura della replica...")
                            os._exit(0)
                    except json.JSONDecodeError:
                        # Se non è JSON, controlla se contiene la parola shutdown
                        pass
                    
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


def connect_to_broker():
    """Thread che rimane connesso al broker e invia i dati usando SlaveClient"""
    
    try:
        logger.info(f"Connessione al broker {BROKER_HOST}:{BROKER_PORT}")
        slave = SlaveClient(BROKER_HOST, BROKER_PORT)

        # Start receiving data from the custom broker
        slave.run()

    except Exception as e:
        logger.error(f"Error while communicating with broker: {e}")
            


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


if __name__ == '__main__':
    logger.info("Starting Flask app on 0.0.0.0:5000")
    
    # Avvia il thread che rimane connesso al simulatore
    stream_thread = threading.Thread(target=connect_to_upstream, daemon=True)
    stream_thread.start()
    logger.info("Thread di streaming SSE avviato")
    
    # Avvia il thread che invia i dati al broker
    broker_thread = threading.Thread(target=connect_to_broker, daemon=True)
    broker_thread.start()
    logger.info("Thread di connessione al broker avviato")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
