#!/usr/bin/env python

import socket
import sys
from db import DB
db = DB( "jay" )

"""
DROP TABLE power_hawk;
CREATE TABLE power_hawk ( ts TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    amps_1 DOUBLE NOT NULL,
    amps_2 DOUBLE NOT NULL,
    amps_3 DOUBLE NOT NULL,
    amps_4 DOUBLE NOT NULL,
PRIMARY KEY ( ts ) );
"""

# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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
    if len(parts) != 4:
        continue
    amps_1, amps_2, amps_3, amps_4 = parts

    #print(parts)
    db.query("INSERT INTO power_hawk ( amps_1, amps_2, amps_3, amps_4 ) VALUES ( {}, {}, {}, {} );".format(amps_1, amps_2, amps_3, amps_4))
