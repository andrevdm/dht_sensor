import json
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt
from threading import Thread

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.config import Config

latestData = {}
sourceMap = {"10.0.0.31": 'out', "10.0.32": 'in'}


def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))
    client.subscribe("dht_sensor_measurement")


def on_message(client, userdata, msg):
    # print(msg.topic);
    d = json.loads(msg.payload)
    now = datetime.now()
    date_time = now.strftime("%Y/%m/%d, %H:%M:%S")
    d['at'] = date_time
    latestData[d['host']] = d
    print(latestData)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("mqtt.lan", 1883, 60)


def mqtt_loop():
    print("mqtt_loop")
    client.loop_forever()


mqtt_thread = Thread(target=mqtt_loop)
mqtt_thread.start()


async def latest(request):
    # return latestData but lookup id from sourceMap
    d = {}
    for k, v in latestData.items():
        v['source'] = k
        v['at'] = v['at']
        if k in sourceMap:
            d[sourceMap[k]] = v
        else:
            d[k] = v
    print(d)
    return JSONResponse(d)


async def homepage(request):
    return FileResponse('static/index.html')

# Config will be read from environment variables and/or ".env" files.
config = Config(".env")
DEBUG = config('DEBUG', cast=bool, default=False)

app = Starlette(debug=DEBUG, routes=[
    Route('/latest', latest, methods=['GET']),
    Mount('/static', app=StaticFiles(directory='static'), name="static"),
    Route('/', homepage, methods=['GET']),
    Route('/index.html', homepage, methods=['GET']),
])
