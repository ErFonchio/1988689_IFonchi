from flask import Flask, Response, jsonify
import requests
import threading
import logging
import os
import json
import socket
from queue import Queue
from collections import deque
import time
import numpy as np
from datetime import datetime
import numpy as np
from datetime import datetime

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

# Sliding window automatica - mantiene solo gli ultimi n elementi
window_length = 1200
data_window = deque(maxlen=window_length)

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

                measures = json.loads(data.decode())
                '''invio a frontend'''

                data_window.append(measures)
                
                self.count += 1

                if (self.count % 200) == 0:
                    logger.info(f"Received data: {measures}")
            
                if (self.leader == True) and (self.count % window_length) == 0:
                    logger.info(f"entering frequency analysis")
                    frequency_analysis(data_window)

                    '''invio dell'analisi delle frequenze a database + frontend'''

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

def frequency_analysis(data_window):
    '''Analizza frequenze per ogni ID sensore'''
    
    if len(data_window) < 2:
        logger.warning("Non abbastanza dati per l'analisi")
        return None
    
    try:
        # 1. quali id mi sono arrivati?
        window_ids = set([sample['sensor_id'][-2:] for sample in data_window])
        logger.info(f"window_ids {window_ids}")

        data_id = {}
        for id_ in window_ids:
            data_id[id_] = {'timestamps': [], 'values': []}
        
        # 2. Popola data_id con i campioni dalla finestra
        for sample in data_window:
            data = json.loads(sample) if isinstance(sample, str) else sample
            sensor_id = data['sensor_id'][-2:]  # Estrae l'ID dal sample
            data_id[sensor_id]['timestamps'].append(datetime.fromisoformat(data['timestamp']))
            data_id[sensor_id]['values'].append(float(data['value']))

        # 3. Analizza ogni sensore
        results = {}
        for sensor_id, sensor_data in data_id.items():
            logger.info(f"Analizzando le frequenze di {sensor_id}")
            timestamps = sensor_data['timestamps']
            values = sensor_data['values']
            
            if len(timestamps) < 2:
                results[sensor_id] = {'error': 'Not enough data', 'sample_count': 0}
                logger.warning(f"Not enough timestamps per id {sensor_id}")
                continue
            
            
            # Calcola intervallo temporale medio (sample rate)
            time_diffs = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                          for i in range(len(timestamps)-1)]
            avg_dt = np.mean(time_diffs)
            sample_rate = 1 / avg_dt if avg_dt > 0 else 1
            
            # FFT per trovare frequenza dominante
            fft_values = np.fft.fft(values)
            freqs = np.fft.fftfreq(len(values), avg_dt)
            power = np.abs(fft_values) ** 2
            
            # Prendi solo frequenze positive
            idx = np.where(freqs > 0)[0]
            dominant_freq = freqs[idx][np.argmax(power[idx])]

            # sensor_ id, event_type, interval_start, interval_end, frequency
            
            results[sensor_id] = {
                'sensory_id': sensor_id,
                'event_type': "earthquake" if 0.5 <= dominant_freq < 3.0 else ("conventional-explosion" if 3.0 <= dominant_freq < 8.0 else ("base" if dominant_freq < 0.5 else "nuclear-like")),
                'interval_start': timestamps[0],
                'interval_end': timestamps[-1], 
                'dominant_frequency': dominant_freq,
            }
            
            logger.info(f"Sensore {sensor_id}: freq={dominant_freq:.2f} Hz, event_type {results[sensor_id]['event_type']}")
        
        return results
        
    except Exception as e:
        logger.error(f"Errore nell'analisi: {e}")
        return None

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
