#!/usr/bin/env python

import socket
import sys

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to the port
server_address = ('', 10243)
print('starting up on %s port %s' % server_address)
sock.bind(server_address)

while True:
    # print('\nwaiting to receive message')
    data, address = sock.recvfrom(4096)
    #print(data)
    msg = data.decode('utf-8')

    parts = [float(v) for v in msg.split(',')]
    print(parts)
