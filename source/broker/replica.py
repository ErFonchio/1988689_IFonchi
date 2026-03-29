import socket 
import json 

ACK = b"ACK"

PORT = 5000 
HOST = "127.0.0.1"

class SlaveClient:
    def __init__(self, master_host: str, master_port: int):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((master_host, master_port))

    def run(self):
        while True:
            data = self.sock.recv(4096)
            measures = json.loads(data.decode())
            if not data:
                break 
            print(f"Received: {measures}")
            self.sock.sendall(ACK)
        self.sock.close()



if __name__ == "__main__": 
    slave = SlaveClient(master_host=HOST, master_port=PORT)
    slave.run()