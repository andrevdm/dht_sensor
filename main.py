import machine
import time
import dht 
import network
import urequests

sensor = dht.DHT22(machine.Pin(14))
sensor.measure()

import gc

while True:
  response = None
  try:
    gc.collect()
    sensor.measure()
    temp = sensor.temperature()

    hum = sensor.humidity()
    print('Temperature: %3.1f C' %temp)
    print('Humidity: %3.1f %%' %hum)

    #response = urequests.post("https://eofolflaso7m4kq.m.pipedream.net", data = "id=202&temp=%3.1f,hum=%3.1f" %(temp, hum))
    response = urequests.post("http://192.168.68.201/dht", data = '{"id":202, "temp": %3.1f, "hum": %3.1f}' %(temp, hum))
    response.close()
  except Exception as e:
    print("An exception occurred:", e)
    if isinstance(e, OSError) and response: # If the error is an OSError the socket has to be closed.
      response.close()

  gc.collect()
  time.sleep(5)

