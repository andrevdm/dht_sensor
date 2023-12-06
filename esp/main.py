import gc
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

sensor23 = dht.DHT22(machine.Pin(23))
sensor23.measure()


client_id = ubinascii.hexlify(machine.unique_id())
client_id_str = ubinascii.hexlify(machine.unique_id()).decode('utf-8')

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


try:
    data = '{"host": "%s", "client_id": "%s", "event": "starting"}' % (ip, client_id_str)
    client.publish("dht_sensor_events", data)
except OSError as e:
    print("OSError: %s" % e)


wdt = machine.WDT(timeout=15000)
wdt.feed()

while True:
    gc.collect()
    wdt.feed()

    try:
        client.check_msg()
        if (time.time() - last_measure) > measure_interval:
            sensor23.measure()
            temp14 = sensor23.temperature()
            hum14 = sensor23.humidity()
            data14 = '{"host": "%s", "client_id": "%s", "sensor": %d, "temp": %3.1f, "hum": %3.1f}' % (ip, client_id_str, 14, temp14, hum14)
            print(data14)

            client.publish(topic_sensor_pub, data14)
            last_measure = time.time()

        time.sleep(5)
    except OSError as e:
        restart_and_reconnect()
