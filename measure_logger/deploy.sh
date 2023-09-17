#/bin/bash
set -e
./copy.sh
ssh 192.168.68.201 sudo systemctl restart dht_logger.service
