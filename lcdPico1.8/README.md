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

Backlight Control (JSON only)
- Publish JSON to topic dht_sensor_lcd_backlight
- Fields: "mode": "on" | "off" | "auto" | "reset"; optional "weekday_on","weekday_off","weekend_on","weekend_off" (HH:MM)
- "reset" reloads env/default times and clears override (returns to auto).
- Non-retained publishes recommended so reboot returns to schedule.

Examples
1. Force backlight ON:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"on"}'
2. Force backlight OFF:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"off"}'
3. Return to scheduled auto:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"auto"}'
4. Reset (restore times + auto):
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"reset"}'
5. Update weekday schedule (stay auto):
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"weekday_on":"06:45","weekday_off":"23:15"}'
6. Update weekend schedule and force ON:
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"on","weekend_on":"09:00","weekend_off":"22:30"}'
7. Change both schedules (auto):
   mqtt pub -h mqtt.lan -t dht_sensor_lcd_backlight -m '{"mode":"auto","weekday_on":"07:00","weekday_off":"22:15","weekend_on":"09:30","weekend_off":"23:00"}'

Config Topic JSON Fields
{"metric":"temp"|"hum"|"humidity", "period":"1hours" (e.g. 15minutes, 2hours), "count":24}

Rotation Topic Example
mqtt pub -h mqtt.lan -t dht_sensor_lcd_rotation -m '{"rotation":90}'

Notes
- Time printed once at startup shows local (UTC + simplified DST) and backlight state.
- Override suppresses schedule until mode auto is received.
- Schedule updates take effect immediately; next minute tick applies new window.
