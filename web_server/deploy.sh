#/bin/bash
set -e
scp dhtServer.py 192.168.68.201:/home/andre/dhtServer/dhtServer.py
ssh 192.168.68.201 sudo systemctl restart dht.service
