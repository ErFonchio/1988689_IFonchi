import json, requests
import asyncio, websockets
from concurrent.futures import ThreadPoolExecutor

### First retireve devices
url = "http://localhost:8080/api/devices"

response = requests.get(url)

if response.status_code == 200:
    devices = response.json()

# retrieve web_sockets urls
ws_urls = {}

for device in devices:
    ws_urls[device['id']] = device['websocket_url']


### Get measurment data from sensors

# We try to read data concurrently, starting 12 different threads, one for each sensor.

async def get_measures(sensor_id):
    ws_url = f'ws://localhost:8080/api/device/{sensor_id}/ws'
    async with websockets.connect(ws_url) as websocket:

        while True:
            measurement = await websocket.recv()

            with open(f'data/{sensor_id}.jsonl', 'a') as f:
                f.write(json.dumps(json.loads(measurement)) + '\n')



def start_reading(sensor_id):
    asyncio.run(get_measures(sensor_id))



def run():
    '''
        Start 12 different threads that concurrently read measures from sensors.
    '''
    with ThreadPoolExecutor(max_workers=12) as executor:
        sensors = ws_urls.keys()
        for sensor_id in sensors:
            executor.submit(start_reading, sensor_id)


if __name__ == '__main__':
    run()
