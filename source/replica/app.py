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

class SlaveClient:
    """Client slave che si connette al broker master"""
    def __init__(self, master_host: str, master_port: int, max_retries: int = 10):
        self.sock = None
        self.max_retries = max_retries
        self._connect(master_host, master_port)
    
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

    def send_data(self, data: str):
        """Invia dati al master e aspetta ACK"""
        try:
            self.sock.sendall(data.encode() + b"\n")
            ack = self.sock.recv(len(ACK))
            if ack == ACK:
                logger.debug("ACK ricevuto dal broker")
                return True
            else:
                logger.warning(f"ACK invalido dal broker: {ack}")
                return False
        except Exception as e:
            logger.error(f"Errore invio dati: {e}")
            return False

    def close(self):
        """Chiude la connessione"""
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
    
    while True:
        try:
            logger.info(f"Connessione al broker {BROKER_HOST}:{BROKER_PORT}")
            slave = SlaveClient(BROKER_HOST, BROKER_PORT)
            
            while True:
                # Leggi dalla coda SSE e invia al broker
                try:
                    data = sse_queue.get(timeout=5)
                    # Rimuovi prefisso SSE e invia il JSON puro
                    line = data.replace("data: ", "").replace("\n\n", "").strip()
                    
                    if line and line != ":":  # Ignora heartbeat
                        logger.debug(f"Inviando al broker: {line}")
                        if not slave.send_data(line):
                            # Errore invio, riconnetti
                            break
                            
                except socket.timeout:
                    logger.debug("Timeout in attesa di dati dalla coda")
                    continue
                except Exception as e:
                    logger.error(f"Errore in slave client: {e}")
                    break
                    
        except ConnectionRefusedError:
            logger.error(f"Broker non raggiungibile ({BROKER_HOST}:{BROKER_PORT}), riprovo...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Errore connessione broker: {e}")
            time.sleep(5)
        finally:
            try:
                slave.close()
            except:
                pass


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
