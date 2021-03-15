#!/usr/bin/env python

import socket
#import sys
from pandas import Timestamp, Timedelta

# Sump is on channel 4
#class Logger:
    


# Create a TCP/IP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Bind the socket to the port
server_address = ('', 10243)
print('starting up on %s port %s' % server_address)
sock.bind(server_address)


cur_logfile_date = None
logfd = None

while True:
    # print('\nwaiting to receive message')
    data, address = sock.recvfrom(4096)
    #print(data)
    msg = data.decode('utf-8')

    parts = [float(v) for v in msg.split(',')]
    if len(parts) != 4:
        continue
    amps_1, amps_2, amps_3, amps_4 = parts

    nowstr = str(Timestamp('now'))
    datestr = nowstr[:10]
    #datestr = nowstr[:18]
    
    if cur_logfile_date != datestr:
        if cur_logfile_date is not None:
            print(f"Closing log {cur_logfile_date}")
            logfd.close()
        cur_logfile_date = datestr
        print(f"Opening log {cur_logfile_date}")
        logfd = open(f"logs/{datestr}_housepower.csv", "w")
        print("ts,amps1,amps2,amps3,amps4", file=logfd)

    print(f"{nowstr},{amps_1},{amps_2},{amps_3},{amps_4}", file=logfd)
    logfd.flush()
    #db.query("INSERT INTO power_hawk ( amps_1, amps_2, amps_3, amps_4 ) VALUES ( {}, {}, {}, {} );".format(amps_1, amps_2, amps_3, amps_4))
