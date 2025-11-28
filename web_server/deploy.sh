#!/bin/bash
set -e
./copy.sh
ssh 192.168.68.199 "sudo cp /home/andre/dhtHost/web_server/dht_web.service /etc/systemd/system/; sudo systemctl daemon-reload; sudo systemctl restart dht_web.service"
