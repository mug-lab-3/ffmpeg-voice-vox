
import socket
import time

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('127.0.0.1', 3000))
s.listen(1)
print("Holding 3000...")
try:
    while True:
        time.sleep(1)
except:
    pass
