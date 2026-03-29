import json, requests
import asyncio, websockets
from concurrent.futures import ThreadPoolExecutor
import socket
import threading
import time 
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

### First retireve the devices
url = "http://localhost:8080/api/devices"

response = requests.get(url)

if response.status_code == 200:
    devices = response.json()

# retrieve web_sockets urls
ws_urls = {}

for device in devices:
    ws_urls[device['id']] = device['websocket_url']


### CLASSES FOR HANDLING CONNECTION WITH SLAVES

ACK = b"ACK"
ACK_TIMEOUT = 5.0 
HEARTBEAT_INTERVAL = 10.0

PORT = 5000 
HOST = "127.0.0.1"

class SlaveConnection:
    def __init__(self, conn: socket.socket, slave_id: int, addr):
        self.conn = conn 
        self.slave_id = slave_id
        self.addr = addr 
        self.alive = True 
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
                ack = self.conn.recv(len(ACK))  # len(ACK) buffer size
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

    ## Set-up connection

    def accept_connection(self):
        '''
            Listen for incoming connections from slaves
        '''
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen(self.num_slaves)
            logger.info(f"Master listening on {self.host}: {self.port}")

            while True:
                conn, addr = server.accept()
                slave = SlaveConnection(conn, self.slave_id, addr)
                self.slave_id += 1

                with self.slaves_lock:
                    self.slaves.append(slave)
                
                logger.info(f"Slave {slave.slave_id} connected. Total: {len(self.slaves)} slaves")
        
    
    def broadcast(self, data: bytes):
        threads, results = [], {}

        with self.slaves_lock:
            active_slaves = [s for s in self.slaves if s.alive]

        # broadcast data to active slaves
        def send(slave: SlaveConnection):
            results[slave.slave_id] = slave.send_and_ack(data)

        for slave in active_slaves:
            t = threading.Thread(target=send, args=(slave,), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        with self.slaves_lock:
            crushed = [s for s in active_slaves if not s.alive]
            
            # update slaves
            self.slaves = [s for s in self.slaves if s.alive]

        for s in crushed:
            logger.warning(f"Removing crushed slave {s.slave_id}")
            s.close()

        success = sum(1 for ok in results.values() if ok)
        logger.info(f"Broadcast: {success}/{len(results)} slaves ACKed")
        return results
    
    def run(self, data_source):
        threading.Thread(target=self.accept_connection, daemon=True).start()
        self.broadcast(data_source)

        


### Get measurment data from sensors

# We try to read data concurrently, starting 12 different threads, one for each sensor.

async def get_measures(sensor_id, master: Master):
    ws_url = f'ws://localhost:8080/api/device/{sensor_id}/ws'
    async with websockets.connect(ws_url) as websocket:

        while True:
            #print("Receiving data...")
            measurement = await websocket.recv()

            #with open(f'data/{sensor_id}.jsonl', 'a') as f:
                # f.write(json.dumps(json.loads(measurement)) + '\n')
            data = json.dumps(json.loads(measurement)).encode()
            #print(data)
            master.broadcast(data)



def start_reading(sensor_id, master):
    asyncio.run(get_measures(sensor_id, master))



def run(master: Master):
    '''
        Start 12 different threads that concurrently read measures from sensors.
    '''
    with ThreadPoolExecutor(max_workers=12) as executor:
        sensors = ws_urls.keys()
        for sensor_id in sensors:
            executor.submit(start_reading, sensor_id, master)


async def start():
    master = Master(host=HOST, port=PORT, num_slaves=5)

    threading.Thread(target=master.accept_connection, daemon=True).start()

    # Start threads for reading data
    run(master)

if __name__ == '__main__':
    asyncio.run(start())

