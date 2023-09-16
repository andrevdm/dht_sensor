# boot.py -- run on boot-up
import machine
import time
import network

import gc
gc.collect()

ssid = 'BobsHauntedGecko'
password = 'tkgr6073'

print('Connecting...')

station = network.WLAN(network.STA_IF)

station.active(True)
station.connect(ssid, password)

while station.isconnected() == False:
  pass

print('Connection successful')
print(station.ifconfig())

