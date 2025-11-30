Scripted Uploads (iso-lcd.lan)
- Upload code.py:
  - curl --fail -u :changeme -X PUT --data-binary @code.py http://iso-lcd.lan/fs/code.py
- Upload a library:
  - curl --fail -u :changeme -X PUT --data-binary @lib/adafruit_minimqtt/adafruit_minimqtt.mpy http://iso-lcd.lan/fs/lib/adafruit_minimqtt/adafruit_minimqtt.mpy
- Upload fonts/assets:
  - curl --fail -u :changeme -X PUT --data-binary @fonts/MonaspaceNeon8.bdf http://iso-lcd.lan/fs/fonts/MonaspaceNeon8.bdf
- List files:
  - curl --fail -u :changeme http://iso-lcd.lan/fs/
- Delete:
  - curl --fail -u :changeme -X DELETE http://iso-lcd.lan/fs/lib/oldlib.mpy

MQTT Topics
- Sensor measurements (subscribe only): dht_sensor_measurement
- Unified config (metric/period/count): dht_sensor_lcd_control
- Rotation control: dht_sensor_lcd_rotation
- Backlight override & schedule: dht_sensor_lcd_backlight

Backlight Override
- Modes: on, off, auto (auto = follow weekday/weekend schedule)
- Non-retained publishes recommended so reboot returns to schedule.

Examples
1. Force backlight ON:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m on
2. Force backlight OFF:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m off
3. Return to scheduled auto:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m auto
4. JSON with override:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"off"}'
5. Update weekday schedule (keep auto):
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"weekday_on":"07:15","weekday_off":"21:45"}'
6. Update weekend schedule:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"weekend_on":"09:30","weekend_off":"23:00"}'
7. Combined schedule + override:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"on","weekend_on":"09:00","weekend_off":"22:30"}'

Config Topic JSON Fields
{"metric":"temp"|"hum"|"humidity", "period":"1hours" (e.g. 15minutes, 2hours), "count":32}

Rotation Topic Example
mqtt pub -h mqtt.lan -t dht_sensor_lcd_rotation -m '{"rotation":90}'

Notes
- Time printed once at startup shows local (UTC + simplified DST) and backlight state.
- Override suppresses schedule until mode auto is received.
- Schedule updates take effect immediately; next minute tick applies new window.
