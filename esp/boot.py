# boot.py -- run on boot-up
import machine
import time
import network
import urequests
from umqttsimple import MQTTClient
import ubinascii
import micropython
import esp

esp.osdebug(None)

import gc
gc.collect()

ssid = 'BobsHauntedGecko'
password = 'tkgr6073'
mqtt_server = '192.168.68.199'

print('Connecting...')

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

ip = station.ifconfig()[0]
