#!/bin/bash
set -e
./copy.sh
ssh 192.168.68.199 "sudo cp /home/andre/dhtHost/measure_logger/dht_logger.service /etc/systemd/system; sudo systemctl daemon-reload; sudo systemctl restart dht_logger.service"

