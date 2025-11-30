import time, os, json
import board, busio, digitalio, displayio
from adafruit_display_text import bitmap_label
from adafruit_bitmap_font import bitmap_font
from fourwire import FourWire
import adafruit_st7735r
import terminalio
import wifi, socketpool
import adafruit_requests
from adafruit_minimqtt import adafruit_minimqtt as MQTT
from adafruit_display_shapes.sparkline import Sparkline
from adafruit_display_shapes.line import Line
import rtc

MQTT_BROKER = "mqtt.lan"
MQTT_PORT = 1883
MQTT_TOPIC = "dht_sensor_measurement"
MQTT_CTRL_TOPIC = "dht_sensor_lcd_control"
MQTT_CONFIG_TOPIC = MQTT_CTRL_TOPIC  # reuse legacy control topic for config
MQTT_ROTATION_TOPIC = "dht_sensor_lcd_rotation"

HOST_OUT = "10.0.0.31"  # external
HOST_IN = "10.0.0.32"  # internal

# Config: select metric 'temp' or 'hum'
METRIC = os.getenv("METRIC") or "temp"

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

# Charts group (on-screen)
charts_group = displayio.Group()
group.append(charts_group)

OUT_COLOR = 0x3399FF
IN_COLOR = 0x33CC66
INFO_COLOR = 0xCCCCCC
AXIS_COLOR = 0x666666

# Load smaller bitmap font for better fit
font = bitmap_font.load_font("/fonts/MonaspaceNeon8.bdf")
clock_font = bitmap_font.load_font("/fonts/MonaspaceNeon6.bdf")

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

# Small clock under IN row (HH:MM)
clock_label = bitmap_label.Label(clock_font, text="--:--", color=INFO_COLOR, scale=1)
clock_label.anchor_point = (1.0, 0.0)
clock_label.anchored_position = (display.width - 4, 28)
group.append(clock_label)

# --- Single Sparkline ---
# Dimensions for rotation=90 on 160x128: leave ~30px top for text
chart_width = display.width - 8
chart_x = 4
chart_y = 44  # center one chart below labels
chart_h = 76  # taller single chart

TEMP_MIN, TEMP_MAX = 10.0, 35.0
HUM_MIN, HUM_MAX = 20.0, 100.0

# Stage builder: one chart based on METRIC


def build_staged_charts(buckets):
    stage = displayio.Group()

    # Collect metric values from buckets (IN + OUT)
    vals = []
    if buckets:
        for item in buckets:
            if METRIC == "hum" or METRIC == "humidity":
                iv = item.get("in_humidity")
                ov = item.get("out_humidity")
            else:
                iv = item.get("in_temp")
                ov = item.get("out_temp")
            if iv is not None:
                vals.append(float(iv))
            if ov is not None:
                vals.append(float(ov))

    # Determine exact bounds (no padding)
    if vals:
        vmin = min(vals)
        vmax = max(vals)
    else:
        vmin, vmax = (
            (HUM_MIN, HUM_MAX)
            if METRIC in ("hum", "humidity")
            else (TEMP_MIN, TEMP_MAX)
        )

    if (vmax - vmin) < 1e-6:
        vmax = vmin + 1.0

    mid = (vmin + vmax) / 2.0

    # Sparklines (IN/OUT overlaid)
    sp_in = Sparkline(
        width=chart_width,
        height=chart_h,
        max_items=chart_width,
        x=chart_x,
        y=chart_y,
        color=IN_COLOR,
    )
    sp_out = Sparkline(
        width=chart_width,
        height=chart_h,
        max_items=chart_width,
        x=chart_x,
        y=chart_y,
        color=OUT_COLOR,
    )
    stage.append(sp_in)
    stage.append(sp_out)

    # Axis ticks and labels (top/mid/bottom) with one-decimal values
    axis = (
        (chart_y, f"{vmax:.1f}"),
        (chart_y + chart_h // 2, f"{mid:.1f}"),
        (chart_y + chart_h - 1, f"{vmin:.1f}"),
    )
    for y, text in axis:
        stage.append(Line(chart_x - 2, y, chart_x + chart_width, y, AXIS_COLOR))
        lbl = bitmap_label.Label(font, text=text, color=AXIS_COLOR, scale=1)
        lbl.x = 0
        lbl.y = y
        stage.append(lbl)
    # Right-edge subtle tick to indicate newest side
    rx = chart_x + chart_width - 1
    ry1 = chart_y + chart_h // 2 - 4
    ry2 = chart_y + chart_h // 2 + 4
    stage.append(Line(rx, ry1, rx, ry2, AXIS_COLOR))
    # Subtle bottom baseline cue
    stage.append(
        Line(
            chart_x,
            chart_y + chart_h - 1,
            chart_x + chart_width,
            chart_y + chart_h - 1,
            AXIS_COLOR,
        )
    )

    # Fill series from buckets according to metric (forward so newest ends up on the right)
    if buckets:
        # Forward iteration: add oldest first, newest last -> newest at rightmost pixel
        for idx in range(0, len(buckets)):
            item = buckets[idx]
            if METRIC in ("hum", "humidity"):
                iv = item.get("in_humidity")
                ov = item.get("out_humidity")
                if iv is not None:
                    sp_in.add_value(norm(float(iv), vmin, vmax, sp_in.height))
                if ov is not None:
                    sp_out.add_value(norm(float(ov), vmin, vmax, sp_out.height))
            else:
                iv = item.get("in_temp")
                ov = item.get("out_temp")
                if iv is not None:
                    sp_in.add_value(norm(float(iv), vmin, vmax, sp_in.height))
                if ov is not None:
                    sp_out.add_value(norm(float(ov), vmin, vmax, sp_out.height))
    return stage


def swap_charts(new_group):
    global charts_group
    try:
        group.remove(charts_group)
    except Exception:
        pass
    charts_group = new_group
    group.append(charts_group)


# Normalize helper


def norm(val, vmin, vmax, height):
    if val is None:
        return None
    if val < vmin:
        val = vmin
    if val > vmax:
        val = vmax
    # Invert mapping: higher values -> smaller y offset (toward top labeled vmax)
    return (height - 1) - int((val - vmin) * (height - 1) / (vmax - vmin))


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


def update_clock():
    try:
        tm = time.localtime()
        clock_label.text = f"{tm.tm_hour:02d}:{tm.tm_min:02d}"
    except Exception:
        pass


# ---- WiFi ----


def connect_wifi():
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    pwd = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    if not ssid:
        raise RuntimeError("CIRCUITPY_WIFI_SSID not set in settings.toml")
    wifi.radio.connect(ssid, pwd)
    return socketpool.SocketPool(wifi.radio)


pool = None
session = None


def ensure_wifi():
    global pool, session
    try:
        if not pool:
            pool = connect_wifi()
            # Build HTTP session for bucket fetches (http, no SSL)
            session = adafruit_requests.Session(pool, None)
    except Exception as e:
        print("WiFi connect failed:", e)
        time.sleep(2)


mqtt = None


def handle_message(client, topic, msg):
    global \
        METRIC, \
        BUCKET_PERIOD, \
        BUCKET_COUNT, \
        last_bucket_fetch, \
        last_age_refresh, \
        chart_width, \
        chart_x, \
        chart_y, \
        chart_h
    # Basic diagnostics
    try:
        print("MQTT msg:", topic, "len=", len(msg) if msg else 0)
    except Exception:
        pass

    # New config topic handling
    if topic == MQTT_CONFIG_TOPIC:
        print("CONFIG recv:", msg)
        try:
            cfg = json.loads(msg)
        except Exception as e:
            print("Bad JSON on", topic, ":", e)
            return
        # Required fields
        if not all(k in cfg for k in ("metric", "period", "count")):
            print("CONFIG missing fields; ignoring")
            return
        m = cfg.get("metric")
        p = cfg.get("period")
        c = cfg.get("count")

        if m in ("temp", "hum", "humidity"):
            METRIC = "temp" if m == "temp" else "hum"
        # Period normalization
        if isinstance(p, str) and p:
            try:
                ps = p.strip().lower()
                i = 0
                while i < len(ps) and ps[i].isdigit():
                    i += 1
                num = ps[:i] or "1"
                unit = ps[i:]
                if unit in ("min", "mins", "minute", "minutes"):
                    unit = "minutes"
                elif unit in ("hour", "hours"):
                    unit = "hours"
                elif unit in ("day", "days"):
                    unit = "days"
                elif unit in ("week", "weeks"):
                    unit = "weeks"
                BUCKET_PERIOD = f"{num}{unit}"
            except Exception:
                BUCKET_PERIOD = p
        if isinstance(c, int):
            max_items = chart_width
            BUCKET_COUNT = max(1, min(c, max_items))
        print("CONFIG applied:", METRIC, BUCKET_PERIOD, BUCKET_COUNT)
        # Immediate clear and fetch
        try:
            empty_stage = build_staged_charts([])
            swap_charts(empty_stage)
        except Exception as e:
            print("CONFIG clear failed:", e)
        last_age_refresh = time.monotonic()
        try:
            if session:
                resp = session.get(
                    BUCKET_URL.format(period=BUCKET_PERIOD, count=BUCKET_COUNT)
                )
                data = resp.json()
                resp.close()
                stage = build_staged_charts(data)
                swap_charts(stage)
                last_bucket_fetch = time.monotonic()
        except Exception as e:
            print("CONFIG fetch failed:", e)
        return
    # Rotation topic handling
    if topic == MQTT_ROTATION_TOPIC:
        print("ROTATION recv:", msg)
        try:
            rot_payload = json.loads(msg)
        except Exception as e:
            print("Bad JSON on", topic, ":", e)
            return
        rot = rot_payload.get("rotation")
        if isinstance(rot, int) and rot in (0, 90, 180, 270):
            try:
                if display.rotation != rot:
                    display.rotation = rot
                    # Recalc layout dims
                    # chart dimensions updated below; globals declared at function start
                    chart_width = display.width - 8
                    chart_x = 4
                    chart_y = 44
                    chart_h = (
                        display.height - chart_y - 8
                        if (display.height - chart_y - 8) > 10
                        else chart_h
                    )
                    empty_stage = build_staged_charts([])
                    swap_charts(empty_stage)
                    # Optional fresh bucket fetch
                    if session:
                        resp = session.get(
                            BUCKET_URL.format(period=BUCKET_PERIOD, count=BUCKET_COUNT)
                        )
                        data = resp.json()
                        resp.close()
                        stage = build_staged_charts(data)
                        swap_charts(stage)
                        last_bucket_fetch = time.monotonic()
                print("ROTATION applied:", rot)
            except Exception as e:
                print("ROTATION apply failed:", e)
        else:
            print("ROTATION invalid:", rot)
        return
        # (Legacy control branch removed; unified config uses MQTT_CONFIG_TOPIC)
        if isinstance(c, int):
            max_items = chart_width
            BUCKET_COUNT = max(1, min(c, max_items))
        print("CTRL applied:", METRIC, BUCKET_PERIOD, BUCKET_COUNT)
        # Immediate visual feedback: clear chart (axes only)
        try:
            empty_stage = build_staged_charts([])
            swap_charts(empty_stage)
        except Exception as e:
            print("CTRL clear failed:", e)
        # Reset timers and fetch now
        last_age_refresh = time.monotonic()
        try:
            if session:
                resp = session.get(
                    BUCKET_URL.format(period=BUCKET_PERIOD, count=BUCKET_COUNT)
                )
                data = resp.json()
                resp.close()
                stage = build_staged_charts(data)
                swap_charts(stage)
                last_bucket_fetch = time.monotonic()
        except Exception as e:
            print("CTRL fetch failed:", e)
        return

    # Sensor topic handling
    print("SENSOR recv")
    try:
        data = json.loads(msg)
    except Exception as e:
        print("Bad JSON on", topic, ":", e)
        return

    host = data.get("host")
    temp = data.get("temp")
    hum = data.get("hum")

    if host is None:
        print("SENSOR missing host; ignoring")
        return

    ts = time.time()
    if host == HOST_OUT:
        if temp is not None:
            last_out["temp"] = float(temp)
        if hum is not None:
            last_out["hum"] = float(hum)
        if (temp is not None) or (hum is not None):
            last_out["ts"] = ts
    elif host == HOST_IN:
        if temp is not None:
            last_in["temp"] = float(temp)
        if hum is not None:
            last_in["hum"] = float(hum)
        if (temp is not None) or (hum is not None):
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
            mqtt.subscribe(MQTT_CTRL_TOPIC)  # control/config (unified)
            if MQTT_CONFIG_TOPIC != MQTT_CTRL_TOPIC:
                mqtt.subscribe(MQTT_CONFIG_TOPIC)
            mqtt.subscribe(MQTT_ROTATION_TOPIC)
            print(
                "MQTT connected/subscribed:",
                MQTT_TOPIC,
                MQTT_CTRL_TOPIC,
                MQTT_ROTATION_TOPIC,
            )
        except Exception as e:
            print("MQTT connect failed:", e)
            mqtt = None
            time.sleep(2)


# Initial draw
update_ui()
# Initial clock draw
update_clock()

# Optional NTP once
try:
    import adafruit_ntp

    ntp = adafruit_ntp.NTP(connect_wifi(), server="pool.ntp.org", tz_offset=0)
    rtc.RTC().datetime = ntp.datetime
    update_clock()
except Exception as e:
    print("NTP failed:", e)

last_age_refresh = time.monotonic()
last_bucket_fetch = 0
last_clock_min = -1
BUCKET_PERIOD = "1hours"
BUCKET_COUNT = 32
BUCKET_URL = "http://rpi5.lan:8071/bucket/{period}/{count}"

# Initial bucket fetch
try:
    ensure_wifi()
    if session:
        url = BUCKET_URL.format(period=BUCKET_PERIOD, count=BUCKET_COUNT)
        print("FETCH URL:", url)
        resp = session.get(url)
        data = resp.json()
        resp.close()
        # Build stage off-screen and swap in one go
        stage = build_staged_charts(data)
        swap_charts(stage)
        last_bucket_fetch = time.monotonic()
except Exception as e:
    print("Bucket fetch failed:", e)

while True:
    ensure_wifi()
    ensure_mqtt()
    # keep mqtt responsive
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

    # refresh clock each minute
    try:
        tm = time.localtime()
        if tm.tm_min != last_clock_min:
            update_clock()
            last_clock_min = tm.tm_min
    except Exception:
        pass

    # bucket fetch every 15 minutes
    if (session is not None) and (time.monotonic() - last_bucket_fetch > 900):
        try:
            resp = session.get(
                BUCKET_URL.format(period=BUCKET_PERIOD, count=BUCKET_COUNT)
            )
            data = resp.json()
            resp.close()
            stage = build_staged_charts(data)
            swap_charts(stage)
            last_bucket_fetch = time.monotonic()
        except Exception as e:
            print("Bucket fetch failed:", e)

    time.sleep(0.1)
