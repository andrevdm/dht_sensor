#!/bin/bash
cd /home/andre/dhtHost/web_server
/usr/local/bin/uvicorn --port 80 --host 0.0.0.0 --reload dhtServer:app

