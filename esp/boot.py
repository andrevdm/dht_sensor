# boot.py -- run on boot-up
import gc
import machine
import time
import network
import urequests
from umqttsimple import MQTTClient
import ubinascii
import micropython
import esp
import network


gc.collect()

ssid = 'BobsHauntedGecko'
password = 'tkgr6073'
mqtt_server = 'mqtt.lan'

print('Connecting...')

station = network.WLAN(network.STA_IF)

station.active(True)

while True:
    try:
        station.connect(ssid, password)
        # break
    except OSError as e:
        print(e)

    if station.isconnected():
        print('Connected')
        break
    else:
        print('Trying again in 1 seconds')
        time.sleep(1)


# while station.isconnected() == False:
#  pass


net = network.WLAN(network.STA_IF)
net.active(True)

print('Connection successful')
print(station.ifconfig())

ip = station.ifconfig()[0]



wlan = network.WLAN(network.STA_IF)
wlan.active(True)

mac = wlan.config('mac')
print(':'.join('{:02x}'.format(b) for b in mac))

esp.osdebug(None)
