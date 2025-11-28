import time, os, json
import board, busio, digitalio, displayio
from adafruit_display_text import bitmap_label
from adafruit_bitmap_font import bitmap_font
from fourwire import FourWire
import adafruit_st7735r
import terminalio
import wifi, socketpool
from adafruit_minimqtt import adafruit_minimqtt as MQTT
from adafruit_display_shapes.sparkline import Sparkline
import rtc


MQTT_BROKER = "mqtt.lan"
MQTT_PORT = 1883
MQTT_TOPIC = "dht_sensor_measurement"

HOST_OUT = "10.0.0.31"  # external
HOST_IN = "10.0.0.32"  # internal

# ---- Display ----
displayio.release_displays()
spi = busio.SPI(clock=board.GP10, MOSI=board.GP11)
bl = digitalio.DigitalInOut(board.GP13)
bl.direction = digitalio.Direction.OUTPUT
bl.value = True
bus = FourWire(
    spi, command=board.GP8, chip_select=board.GP9, reset=board.GP12, baudrate=24_000_000
)

# 160x128, rotation=90 as requested
display = adafruit_st7735r.ST7735R(
    bus, width=160, height=128, colstart=0, rowstart=0, rotation=90, bgr=False
)

group = displayio.Group()
display.root_group = group

# Clear background
bg_bitmap = displayio.Bitmap(display.width, display.height, 1)
bg_palette = displayio.Palette(1)
bg_palette[0] = 0x000000
bg = displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette, x=0, y=0)
group.append(bg)

OUT_COLOR = 0x3399FF
IN_COLOR = 0x33CC66
INFO_COLOR = 0xCCCCCC

# Load smaller bitmap font for better fit
font = bitmap_font.load_font("/fonts/MonaspaceNeon8.bdf")

# OUT row (top)
out_label = bitmap_label.Label(
    font, text="OUT --.-C --.-%  --m", color=OUT_COLOR, scale=1
)
out_label.x = 4
out_label.y = 10
group.append(out_label)

# IN row (top, slight spacing below OUT)
in_label = bitmap_label.Label(
    font, text="IN  --.-C --.-%  --m", color=IN_COLOR, scale=1
)
in_label.x = 4
in_label.y = 22
group.append(in_label)

# --- Sparklines ---
# Dimensions for rotation=90 on 160x128: leave ~30px top for text
chart_width = display.width - 8
chart_x = 4

# Temperature chart (top): overlay two Sparkline series
TEMP_MIN, TEMP_MAX = 10.0, 35.0
spark_temp_in = Sparkline(
    width=chart_width, height=40, max_items=chart_width, x=chart_x, y=36, color=IN_COLOR
)
spark_temp_out = Sparkline(
    width=chart_width,
    height=40,
    max_items=chart_width,
    x=chart_x,
    y=36,
    color=OUT_COLOR,
)
group.append(spark_temp_in)
group.append(spark_temp_out)

# Humidity chart (bottom): overlay two Sparkline series
HUM_MIN, HUM_MAX = 20.0, 100.0
spark_hum_in = Sparkline(
    width=chart_width, height=40, max_items=chart_width, x=chart_x, y=80, color=IN_COLOR
)
spark_hum_out = Sparkline(
    width=chart_width,
    height=40,
    max_items=chart_width,
    x=chart_x,
    y=80,
    color=OUT_COLOR,
)
group.append(spark_hum_in)
group.append(spark_hum_out)


# Normalize helper
def norm(val, vmin, vmax, height):
    if val is None:
        return None
    if val < vmin:
        val = vmin
    if val > vmax:
        val = vmax
    return int((val - vmin) * (height - 1) / (vmax - vmin))


last_out = {"temp": None, "hum": None, "ts": None}
last_in = {"temp": None, "hum": None, "ts": None}


def fmt_line(prefix, temp, hum, ts):
    t = "--.-" if temp is None else f"{temp:.1f}"
    h = "--.-" if hum is None else f"{hum:.1f}"
    age = "--m" if ts is None else f"{max(0, int((time.time() - ts) // 60))}m"
    return f"{prefix} {t}C {h}%  {age}"


def update_ui():
    out_label.text = fmt_line("OUT", last_out["temp"], last_out["hum"], last_out["ts"])
    in_label.text = fmt_line("IN ", last_in["temp"], last_in["hum"], last_in["ts"])


# ---- WiFi ----
def connect_wifi():
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    pwd = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    if not ssid:
        raise RuntimeError("CIRCUITPY_WIFI_SSID not set in settings.toml")
    wifi.radio.connect(ssid, pwd)
    return socketpool.SocketPool(wifi.radio)


pool = None


def ensure_wifi():
    global pool
    try:
        if not pool:
            pool = connect_wifi()
    except Exception as e:
        print("WiFi connect failed:", e)
        time.sleep(2)


mqtt = None


def handle_message(client, topic, msg):
    try:
        data = json.loads(msg)
    except Exception as e:
        print("Bad JSON:", e)
        return

    host = data.get("host")
    temp = data.get("temp")
    hum = data.get("hum")
    ts = time.time()

    if host == HOST_OUT:
        last_out["temp"] = float(temp) if temp is not None else None
        last_out["hum"] = float(hum) if hum is not None else None
        last_out["ts"] = ts
    elif host == HOST_IN:
        last_in["temp"] = float(temp) if temp is not None else None
        last_in["hum"] = float(hum) if hum is not None else None
        last_in["ts"] = ts
    else:
        print("Unknown host:", host)
        return

    update_ui()


def ensure_mqtt():
    global mqtt
    if not pool:
        return
    if mqtt is None:
        try:
            mqtt = MQTT.MQTT(
                broker=MQTT_BROKER,
                port=MQTT_PORT,
                socket_pool=pool,
                keep_alive=60,
            )
            mqtt.on_message = handle_message
            mqtt.connect()
            mqtt.subscribe(MQTT_TOPIC)
            print("MQTT connected/subscribed:", MQTT_TOPIC)
        except Exception as e:
            print("MQTT connect failed:", e)
            mqtt = None
            time.sleep(2)


# Initial draw
update_ui()

# Optional NTP once
try:
    import adafruit_ntp

    ntp = adafruit_ntp.NTP(connect_wifi(), server="pool.ntp.org", tz_offset=0)
    rtc.RTC().datetime = ntp.datetime
except Exception as e:
    print("NTP failed:", e)

last_age_refresh = time.monotonic()
while True:
    ensure_wifi()
    ensure_mqtt()
    if mqtt:
        try:
            mqtt.loop()
        except Exception as e:
            print("MQTT loop error:", e)
            try:
                mqtt.disconnect()
            except Exception:
                pass
            mqtt = None
    # refresh ages every ~10s
    if time.monotonic() - last_age_refresh > 10:
        update_ui()
        last_age_refresh = time.monotonic()
    time.sleep(0.1)
