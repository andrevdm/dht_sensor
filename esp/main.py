import machine
import time
import dht 
import network
import urequests
from umqttsimple import MQTTClient
import ubinascii
import micropython
import esp
from boot import ip

sensor14 = dht.DHT22(machine.Pin(14))
sensor14.measure()

import gc

client_id = ubinascii.hexlify(machine.unique_id())

print(ip)

topic_sensor_cmd = b'dht_sensor_cmd'
topic_sensor_pub = b'dht_sensor_measurement'

def sub_cb(topic, msg):
  print((topic, msg))
  if topic == topic_sensor_cmd:
    print('DHT.cmd: Received %s' % msg)

def connect_and_subscribe():
  global client_id, mqtt_server, topic_sensor_cmd
  client = MQTTClient(client_id, mqtt_server)
  client.set_callback(sub_cb)
  client.connect()
  client.subscribe(topic_sensor_cmd)
  print('Connected to %s MQTT broker, subscribed to %s topic' % (mqtt_server, topic_sensor_cmd))
  return client

def restart_and_reconnect():
  print('Failed to connect to MQTT broker. Reconnecting...')
  time.sleep(10)
  machine.reset()

try:
  client = connect_and_subscribe()
except OSError as e:
  restart_and_reconnect()

last_measure = 0
measure_interval = 15

while True:
  gc.collect()

  try:
    client.check_msg()
    if (time.time() - last_measure) > measure_interval:
      sensor14.measure()
      temp14 = sensor14.temperature()
      hum14 = sensor14.humidity()
      data14 = '{"host": "%s", "sensor": %d, "temp": %3.1f, "hum": %3.1f}' %(ip, 14, temp14, hum14)
      print(data14)

      client.publish(topic_sensor_pub, data14)
      last_measure = time.time()

    time.sleep(5)
  except OSError as e:
    restart_and_reconnect()


