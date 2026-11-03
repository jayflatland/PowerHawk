#!/bin/bash

#source /home/jay/.bashrc
#source /home/jay/.profile

screen -S powerhawk -d -m
screen -S powerhawk -X screen 1
screen -S powerhawk -X screen 2

screen -S powerhawk -p 0 -X stuff $'cd /opt/PowerHawk\n'
screen -S powerhawk -p 0 -X stuff $'./powerhawk_logger.py\n'
screen -S powerhawk -p 1 -X stuff $'cd /opt/PowerHawk/webserver\n'
screen -S powerhawk -p 1 -X stuff $'./server.sh prod\n'
screen -S powerhawk -p 2 -X stuff $'cd /opt/PowerHawk\n'
screen -S powerhawk -p 2 -X stuff $'./wunderground_logger.py\n'

