import json
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt

con = sqlite3.connect("/home/andre/dhtHost/db/dht.db")

with con:
  con.execute("create table if not exists dht (id integer primary key, host text, sensor integer, client_id text, temp real, hum real, ts timestamp default current_timestamp)")

with con:
  con.execute("create index if not exists dht_host on dht (host)")

latestData = {}
sourceMap = {202: 'isopod 1'}


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
  print("Connected with result code "+str(rc))

  # Subscribing in on_connect() means that if we lose the connection and
  # reconnect then subscriptions will be renewed.
  client.subscribe("dht_sensor_measurement")


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
  #print(msg.topic);
  d = json.loads(msg.payload)
  print(d)
  with con:
    con.execute("insert into dht (host, sensor, client_id, temp, hum) values (?, ?, ?, ?, ?)", (d['host'], d['sensor'], d['client_id'], d['temp'], d['hum']))


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("192.168.68.201", 1883, 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_forever()


#async def dht(request):
#  d = await request.json()
#  print(d)
#  now = datetime.now()
#  date_time = now.strftime("%Y/%m/%d, %H:%M:%S")
#  #latestData[d['id']] = {'temp': d['temp'], 'hum': d['hum'], 'at': date_time}
#
#  with con:
#    con.execute("insert into dht (source, temp, hum) values (?, ?, ?)", (d['id'], d['temp'], d['hum']))
#
#  return JSONResponse({'success': True})


#async def latest(request):
#  #return latestData but lookup id from sourceMap
#  d = {}
#  for k, v in latestData.items():
#    v['source'] = k
#    v['at'] = v['at']
#    if k in sourceMap:
#      d[sourceMap[k]] = v
#    else:
#      d[k] = v
#  print(d)
#  return JSONResponse(d)
