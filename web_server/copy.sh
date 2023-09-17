#/bin/bash
set -e
#scp dhtServer.py 192.168.68.201:/home/andre/dhtServer/dhtServer.py
#scp -r static 192.168.68.201:/home/andre/dhtServer/
scp -rp . 192.168.68.201:/home/andre/dhtServer/

