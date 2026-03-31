import json, requests
import asyncio, websockets
import os
from concurrent.futures import ThreadPoolExecutor
import socket
import threading
import time 
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

### First retireve devices
SIMULATOR_HOST = os.getenv('SIMULATOR_HOST', 'localhost')
url = f"http://{SIMULATOR_HOST}:8080/api/devices"

FRONTEND_HOST = os.getenv("FRONTEND_HOST", 'localhost')
FRONTEND_PORT = int(os.getenv("FRONTEND_PORT", 8765))

# Retry fino a 30 secondi per attendere il simulatore
devices = []
max_retries = 6  # 6 tentativi x 5 secondi = 30 secondi
for attempt in range(max_retries):
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            devices = response.json()
            logger.info(f"Dispositivi recuperati al tentativo {attempt + 1}")
            break
    except Exception as e:
        logger.warning(f"Tentativo {attempt + 1}/{max_retries} fallito: {e}")
        if attempt < max_retries - 1:
            time.sleep(5)

# retrieve web_sockets urls
ws_urls = {}

if devices:
    for device in devices:
        ws_urls[device['id']] = device['websocket_url']
    logger.info(f"WebSocket URLs recuperati per {len(ws_urls)} dispositivi")
else:
    logger.warning("Nessun dispositivo trovato dal simulatore!")



###  CONNECTION TO THE GUI

ui_clients = set()
ui_clients_lock = asyncio.Lock()

async def ui_handler(websocket):
    # Register a new UI client and keep the connection alive

    async with ui_clients_lock:
        ui_clients.add(websocket)

    try:
        await websocket.wait_closed()
    finally:
        async with ui_clients_lock:
            ui_clients.discard(websocket)

async def broadcast_to_ui(data: dict):
    # Function to broadcast data to the dashboard

    async with ui_clients_lock:
        clients = list(ui_clients)
    
    if clients:
        message = json.dumps(data)
        await asyncio.gather(*[c.send(message) for c in clients], return_exceptions=True)

async def start_ui_server():
    async with websockets.serve(ui_handler, FRONTEND_HOST, FRONTEND_PORT):   
        await asyncio.Future()  # run forever



### CLASSES FOR HANDLING CONNECTION WITH SLAVES

ACK = b"ACK"
ACK_TIMEOUT = 5.0 
HEARTBEAT_INTERVAL = 10.0

LEADER = b"LEADER"

PORT = 5001  # Socket server per Master-Slave (diverso da REST API)
HOST = "0.0.0.0"  # Ascolta da qualsiasi interfaccia (Docker-ready)

class SlaveConnection:
    def __init__(self, conn: socket.socket, slave_id: int, addr, leader: bool):
        self.conn = conn 
        self.slave_id = slave_id
        self.addr = addr 
        self.alive = True 
        self.leader = False
        self.lock = threading.Lock()    # ← to synchronize threads 

    def send_and_ack(self, data: bytes) -> bool:
        '''
        Send measures and wait 5s for the ACK.
        If the ACK is not received in time, declare replica as dead.
        '''

        with self.lock:
            try:
                self.conn.sendall(data)
                self.conn.settimeout(ACK_TIMEOUT)   # wiat 5s for the ack
                ack = self.conn.recv(len(ACK))      # len(ACK) buffer size
                if ack == ACK:
                    return True 
                
                return False
            
            except (socket.timeout) as e:
                logger.warning(f"No ACK received form slave: {self.slave_id}")
                self.alive = False 
                return False
            
    def close(self):
        self.alive = False 
        try: 
            self.conn.close()
        except OSError:
            pass 


class Master:
    def __init__(self, host: str, port: int, num_slaves: int):
        self.host = host 
        self.port = port 
        self.num_slaves = num_slaves 

        self.slave_id = 1   # we'll use this to assign ids to slaves
        self.slaves: list[SlaveConnection] = []
        self.slaves_lock = threading.Lock()

        self.election_lock = threading.Lock()

        # just for handling printing
        self.count = 1

    ## Set-up connection

    def accept_connection(self):
        '''
            Listen for incoming connections from slaves with retry logic
        '''
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    server.bind((self.host, self.port))
                    server.listen(self.num_slaves)
                    logger.info(f"✓ Master listening on {self.host}:{self.port}")
                    
                    while True:
                        try:
                            conn, addr = server.accept()
                            slave = SlaveConnection(conn, self.slave_id, addr, leader=False)

                            self.slave_id += 1

                            with self.slaves_lock:
                                self.slaves.append(slave)
                            
                            logger.info(f"✓ Slave {slave.slave_id} connected from {addr}. Total: {len(self.slaves)} slaves")
                        except Exception as e:
                            logger.error(f"Errore accettando connessione: {e}")
                            continue
                            
            except socket.error as e:
                retry_count += 1
                logger.warning(f"Socket error al tentativo {retry_count}/{max_retries}: {e}")
                if retry_count < max_retries:
                    time.sleep(2)
                else:
                    logger.error(f"Impossibile bindare su {self.host}:{self.port} dopo {max_retries} tentativi")
                    break
            except Exception as e:
                logger.error(f"Errore critico in accept_connection: {e}")
                break
        
    
    def broadcast(self, data: bytes):
        threads, results = [], {}

        '''
        Before starting to broadcast the data, we check if the system has an active leader.
        If this is not the case we elect a new leader scanning the list of active slaves
        '''

        with self.election_lock:
            leader_elected = False
            with self.slaves_lock:
                # Retrieve active slaves
                active_slaves = [s for s in self.slaves if s.alive]

                # Check if there is an alive leader
                for s in active_slaves:
                    if s.leader:
                        leader_elected = True 
                        break 

            if not leader_elected:
                attempts = 3
                if len(active_slaves) > 0:
                    # elect as leader the first slave in the list
                    for _ in range(attempts):
                        elected = False
                        for s in active_slaves:
                            # communicate to the slave that he is the new leader
                            if s.send_and_ack(LEADER):
                                s.leader = True
                                logger.info(f"Elected leader slave {s.slave_id}") 
                                elected = True
                                break
                            else:
                                logger.warning(f"Something went wrong when tried to elect a new leader")
                        
                        # If successfully elected new leader exit
                        if elected:
                            break


        # broadcast data to active slaves
        def send(slave: SlaveConnection):
            try:
                results[slave.slave_id] = slave.send_and_ack(data)
            except Exception as e:
                logger.warning(f"Error with slave {slave.slave_id}: {e}") # slaves crush while receiving data
                slave.alive = False     # mark slave as dead
                results[slave.slave_id] = False

        for slave in active_slaves:
            t = threading.Thread(target=send, args=(slave,), daemon=True)
            threads.append(t)
            t.start()

        # wait for threads to complete
        for t in threads:
            t.join()

        with self.slaves_lock:
            crushed = [s for s in active_slaves if not s.alive]
            self.slaves = [s for s in self.slaves if s.alive]   # update slaves

        for s in crushed:
            logger.warning(f"Removing crushed slave {s.slave_id}")
            s.close()

        success = sum(1 for ok in results.values() if ok)
        #logger.info(f"Broadcast: {success}/{len(results)} slaves ACKed")
        return results
    
    def run(self, data_source):
        threading.Thread(target=self.accept_connection, daemon=True).start()
        self.broadcast(data_source)

### Get measurement data from sensors

# We try to read data concurrently, starting threads for each sensor,
# and broadcast the data to all connected replicas

async def get_measures(sensor_id, master: Master):
    """
    Legge le misurazioni da un sensore via WebSocket e le invia a tutte le repliche.
    
    Args:
        sensor_id: ID del sensore da cui leggere
        master: Istanza di Master per il broadcast
    """
    ws_url = f'ws://{SIMULATOR_HOST}:8080/api/device/{sensor_id}/ws'
    
    try:
        async with websockets.connect(ws_url) as websocket:
            logger.info(f"✓ Connesso al sensore {sensor_id}")
            
            while True:
                try:
                    # 1. Ricevi la misurazione dal simulatore (JSON)
                    measurement = await websocket.recv()

                    #print(f"MEASUREMENT: {measurement}\n")

                    # transform the json file in a python dictiorary
                    data = json.loads(measurement)

                    # add the sensor id
                    data['sensor_id'] = sensor_id

                    # send data to the GUI
                    await broadcast_to_ui(data)

                    # encode file 
                    data = json.dumps(data).encode()

                    # broadcast data
                    master.broadcast(data)

                except Exception as e:
                    logger.error(f"Errore ricevendo dal sensore {sensor_id}: {e}")
                    break
                    
    except Exception as e:
        logger.error(f"Errore WebSocket per sensore {sensor_id}: {e}")



async def start():
    logger.info("Avvio Broker Master-Slave...")
    master = Master(host=HOST, port=PORT, num_slaves=5)
    
    # Avvia il server socket per accettare connessioni dalle repliche
    accept_thread = threading.Thread(target=master.accept_connection, daemon=False)
    accept_thread.start()
    logger.info("Thread accept_connection avviato")
    
    # Avvia i thread di lettura dei sensori
    #run(master)

    await asyncio.gather(
        start_ui_server(),
        *[get_measures(sid, master) for sid in ws_urls.keys()]
    )

if __name__ == '__main__':
    asyncio.run(start())

