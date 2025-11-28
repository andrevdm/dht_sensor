import time, gc, os, io
import board, busio, digitalio, displayio
from adafruit_display_text import bitmap_label
from adafruit_bitmap_font import bitmap_font
from fourwire import FourWire
import adafruit_st7735r
import wifi, socketpool, adafruit_requests
import adafruit_imageload  # (unused now, kept for later use)
import terminalio
import rtc

# ---- SPI & Display (unchanged) ----
displayio.release_displays()
spi = busio.SPI(clock=board.GP10, MOSI=board.GP11)
bl = digitalio.DigitalInOut(board.GP13)
bl.direction = digitalio.Direction.OUTPUT
bl.value = True
bus = FourWire(
    spi,
    command=board.GP8,
    chip_select=board.GP9,
    reset=board.GP12,
    baudrate=24_000_000,
)
display = adafruit_st7735r.ST7735R(
    bus, width=128, height=128, colstart=1, rowstart=0, rotation=270, bgr=False
)

group = displayio.Group()
display.root_group = group

# ---- Wi-Fi + HTTP Session ----


def connect_wifi():
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    pwd = os.getenv("CIRCUITPY_WIFI_PASSWORD")
    if not ssid:
        raise RuntimeError("Wi-Fi SSID not set in settings.toml")
    wifi.radio.connect(ssid, pwd)
    pool = socketpool.SocketPool(wifi.radio)
    import ssl

    ssl_context = ssl.create_default_context()
    session = adafruit_requests.Session(pool, ssl_context)
    return session, pool


session, pool = connect_wifi()


# -----------------------------------------------------------------
WEATHER_URL = (
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=53.99"
    "&longitude=-8.02"
    "&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
    "&daily=temperature_2m_min,temperature_2m_max,wind_speed_10m_max,precipitation_sum"
    "&timezone=auto"
    "&wind_speed_unit=kmh"
)


def fetch_weather(session):
    resp = session.get(WEATHER_URL)
    data = resp.json()
    resp.close()
    gc.collect()
    current = data.get("current", {})
    daily = data.get("daily", {})
    parsed = {
        "timestamp": time.time(),
        "current": {
            "temp_c": float(current.get("temperature_2m", 0.0)),
            "wind_kmh": float(current.get("wind_speed_10m", 0.0)),
            "humidity_pct": int(current.get("relative_humidity_2m", 0)),
        },
        "daily": {
            "min_temp_c": float(daily.get("temperature_2m_min", [0.0])[0]),
            "max_temp_c": float(daily.get("temperature_2m_max", [0.0])[0]),
            "max_wind_kmh": float(daily.get("wind_speed_10m_max", [0.0])[0]),
            "rain_mm": float(daily.get("precipitation_sum", [0.0])[0]),
        },
    }
    return parsed


weather_data = None
weather_error = None
try:
    weather_data = fetch_weather(session)
except Exception as e:
    weather_error = repr(e)
    print("Weather initial fetch failed:", weather_error)
    print("Weather initial fetch failed:", weather_error)

WEATHER_UPDATE_INTERVAL = 900  # 15 minutes
weather_last_fetch_monotonic = 0
# -----------------------------------------------------


# ---- Font ----
font = bitmap_font.load_font("/fonts/MonaspaceNeon8.bdf")
font10 = bitmap_font.load_font("/fonts/MonaspaceNeon10.bdf")

# ---- Weather Display ----
_weather_labels = []


def build_weather_display(data):
    print("build_weather_display called; data is None?", data is None)
    if data is None:
        return
    # Simplified rows (humidity removed):
    # Row1: current temp | rain
    # Row2: min/max temp | current/max wind
    layout = [
        {
            "icon": "temp1.bmp",
            "values": [("current", "temp_c", "{v:.0f}")],
            "unit": "°C",
            "col": 0,
            "row": 0,
        },
        {
            "icon": "rain.bmp",
            "values": [("daily", "rain_mm", "{v:.1f}")],
            "unit": "mm",
            "col": 1,
            "row": 0,
        },
        {
            "icon": "temp2.bmp",
            "values": [
                ("daily", "min_temp_c", "{v:.0f}"),
                ("daily", "max_temp_c", "{v:.0f}"),
            ],
            "unit": "°C",
            "col": 0,
            "row": 1,
        },
        {
            "icon": "wind.bmp",
            "values": [
                ("current", "wind_kmh", "{v:.0f}"),
                ("daily", "max_wind_kmh", "{v:.0f}"),
            ],
            "unit": "km/h",
            "col": 1,
            "row": 1,
        },
    ]
    base_y = 62
    row_height = 16
    col_x = {0: 8, 1: 60}
    icon_to_text_gap = 2

    global _weather_labels
    _weather_labels = []

    for cell in layout:
        if not cell["values"]:
            continue
        row = cell["row"]
        col = cell["col"]
        y = base_y + row * row_height
        x = col_x[col]
        icon_name = cell["icon"]
        if icon_name:
            try:
                bmp = displayio.OnDiskBitmap("/assets/" + icon_name)
                icon = displayio.TileGrid(bmp, pixel_shader=bmp.pixel_shader, x=x, y=y)
                group.append(icon)
            except Exception as e:
                print("Icon load fail", icon_name, e)
        x += 10 + icon_to_text_gap
        parts = []
        for section, key, fmt in cell["values"]:
            value = data.get(section, {}).get(key, 0)
            try:
                parts.append(fmt.format(v=value))
            except Exception:
                parts.append("Err")
        text = "/".join(parts) + cell["unit"]
        label = bitmap_label.Label(font, text=text, color=0xCCCCCC)
        label.x = x
        label.y = y + 2
        group.append(label)
        _weather_labels.append(
            {"label": label, "values": cell["values"], "unit": cell["unit"]}
        )


def update_weather_display(data):
    if not _weather_labels or data is None:
        return
    for item in _weather_labels:
        label = item["label"]
        parts = []
        for section, key, fmt in item["values"]:
            value = data.get(section, {}).get(key, 0)
            try:
                parts.append(fmt.format(v=value))
            except Exception:
                parts.append("Err")
        label.text = "/".join(parts) + item["unit"]


build_weather_display(weather_data)

# ---- NTP Time Sync (adafruit_ntp) ----
ntp = None
ntp_ok = False
ntp_error = None
try:
    import adafruit_ntp

    ntp = adafruit_ntp.NTP(pool, server="pool.ntp.org", tz_offset=0)  # RTC UTC
    rtc.RTC().datetime = ntp.datetime
    ntp_ok = True
except Exception as e:
    ntp_error = repr(e)

# ---- IE Flag + Time, NL Time, ZA Time ----
# IE flag bmp
ie_flag_bmp = displayio.OnDiskBitmap("/assets/ie.bmp")
ie_flag = displayio.TileGrid(
    ie_flag_bmp, pixel_shader=ie_flag_bmp.pixel_shader, x=8, y=12
)
group.append(ie_flag)

# IE time label to right of flag
ie_label = bitmap_label.Label(
    font10,
    text="00:00",
    color=0x00FF00,
)
ie_label.x = ie_flag.x + ie_flag_bmp.width + 4
ie_label.y = ie_flag.y + 2  # adjusted for taller font

group.append(ie_label)
# IE date label below time
ie_date_label = bitmap_label.Label(
    font,
    text="0000-00-00",
    color=0xFF8200,
)
ie_date_label.x = ie_label.x
ie_date_label.y = ie_label.y + 13  # extra spacing for larger time font

group.append(ie_date_label)

# NL flag and time label below IE date
nl_flag_bmp = displayio.OnDiskBitmap("/assets/nl.bmp")
nl_flag = displayio.TileGrid(
    nl_flag_bmp,
    pixel_shader=nl_flag_bmp.pixel_shader,
    x=ie_flag.x,
    y=ie_date_label.y + 14,
)
group.append(nl_flag)

nl_label = bitmap_label.Label(font, text="00:00", color=0xCCCCCC)
nl_label.x = nl_flag.x + nl_flag_bmp.width + 4
nl_label.y = nl_flag.y + nl_flag_bmp.height // 2 - 2
group.append(nl_label)

# ZA flag and time label to right of NL block
za_flag_bmp = displayio.OnDiskBitmap("/assets/za.bmp")
za_flag = displayio.TileGrid(
    za_flag_bmp,
    pixel_shader=za_flag_bmp.pixel_shader,
    x=nl_label.x + 40,  # horizontal separation from NL time
    y=nl_flag.y,
)
group.append(za_flag)

za_label = bitmap_label.Label(font, text="00:00", color=0xCCCCCC)
za_label.x = za_flag.x + za_flag_bmp.width + 4
za_label.y = za_flag.y + za_flag_bmp.height // 2 - 2
group.append(za_label)


# ---- DST Logic (Europe) ----


def eu_dst(year, month, day, hour):
    """EU DST: last Sunday March 01:00 UTC -> last Sunday Oct 01:00 UTC."""

    def weekday(y, m, d):  # 0=Sunday
        t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4]
        if m < 3:
            y -= 1
        return (y + y // 4 - y // 100 + y // 400 + t[m - 1] + d) % 7

    def last_sunday(y, m):
        for d in range(31, 24, -1):
            if weekday(y, m, d) == 0:
                return d
        return 31

    if month < 3 or month > 10:
        return False
    if 3 < month < 10:
        return True
    if month == 3:
        last = last_sunday(year, 3)
        return day > last or (day == last and hour >= 1)
    last = last_sunday(year, 10)
    return day < last or (day == last and hour < 1)


# ---- Main Loop ----
last_sync_monotonic = time.monotonic()
SYNC_INTERVAL = 3600

while True:
    # Hourly NTP re-sync
    if ntp_ok and (time.monotonic() - last_sync_monotonic > SYNC_INTERVAL):
        try:
            rtc.RTC().datetime = ntp.datetime
            last_sync_monotonic = time.monotonic()
        except Exception:
            ntp_ok = False

    # Weather refresh every 15 minutes
    if (not _weather_labels) or (
        time.monotonic() - weather_last_fetch_monotonic > WEATHER_UPDATE_INTERVAL
    ):
        try:
            weather_data = fetch_weather(session)
            weather_error = None
            if _weather_labels:
                update_weather_display(weather_data)
            else:
                build_weather_display(weather_data)
        except Exception as e:
            weather_error = repr(e)
            if _weather_labels:
                for lbl in _weather_labels:
                    lbl.text = "Err"
        weather_last_fetch_monotonic = time.monotonic()

    utc = time.localtime()  # UTC
    year, month, day, hour = utc.tm_year, utc.tm_mon, utc.tm_mday, utc.tm_hour
    dst = eu_dst(year, month, day, hour)

    epoch = time.mktime(utc)

    # Offsets
    off_ie = 0 + (1 if dst else 0)  # IE
    off_nl = 1 + (1 if dst else 0)  # NL
    off_za = 2  # ZA (no DST)

    t_ie = time.localtime(epoch + off_ie * 3600)
    t_nl = time.localtime(epoch + off_nl * 3600)
    t_za = time.localtime(epoch + off_za * 3600)

    ie_label.text = f"{t_ie.tm_hour:02d}:{t_ie.tm_min:02d}"
    ie_date_label.text = f"{t_ie.tm_year:04d}-{t_ie.tm_mon:02d}-{t_ie.tm_mday:02d}"
    nl_label.text = f"{t_nl.tm_hour:02d}:{t_nl.tm_min:02d}"
    za_label.text = f"{t_za.tm_hour:02d}:{t_za.tm_min:02d}"

    # Sleep until next minute boundary
    now = time.time()
    secs_to_next_minute = 60 - (int(now) % 60)
    time.sleep(secs_to_next_minute)
