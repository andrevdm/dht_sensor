#!/bin/bash
cd /home/andre/dhtServer/
DEUBG=true /usr/local/bin/uvicorn --port 80 --host 0.0.0.0 --reload dhtServer:app

