#/bin/bash
set -e
./copy.sh
ssh 192.168.68.199 sudo systemctl restart dht_logger.service
