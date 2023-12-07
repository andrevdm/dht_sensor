#!/bin/bash
cd /home/andre/dhtHost/web_server
/usr/bin/uvicorn --port 8071 --host 0.0.0.0 --reload dhtServer:app

