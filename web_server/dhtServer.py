import json
import sqlite3
from datetime import datetime
import paho.mqtt.client as mqtt
from threading import Thread

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.config import Config

# Config will be read from environment variables and/or ".env" files.
config = Config(".env")
DEBUG = config("DEBUG", cast=bool, default=False)
DB_PATH = config("DB_PATH", default="../db/dht.db")

# Initialize SQLite for better concurrency (WAL mode)
_con = None
try:
    _con = sqlite3.connect(DB_PATH, timeout=3.0)
    _cur = _con.cursor()
    _cur.execute("PRAGMA journal_mode=WAL;")
    _cur.execute("PRAGMA busy_timeout=3000;")
    _con.commit()
except Exception:
    pass
finally:
    if _con is not None:
        try:
            _con.close()
        except Exception:
            pass

latestData = {}
sourceMap = {"10.0.0.31": "out", "10.0.0.32": "in"}


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("dht_sensor_measurement")


def on_message(client, userdata, msg):
    # print(msg.topic);
    d = json.loads(msg.payload)
    now = datetime.now()
    date_time = now.strftime("%Y/%m/%d, %H:%M:%S")
    d["at"] = date_time
    latestData[d["host"]] = d
    print(latestData)


client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect("mqtt.lan", 1883, 60)


def mqtt_loop():
    print("mqtt_loop")
    client.loop_forever()


mqtt_thread = Thread(target=mqtt_loop)
mqtt_thread.start()


async def latest(request):
    # return latestData but lookup id from sourceMap
    d = {}
    for k, v in latestData.items():
        v["source"] = k
        v["at"] = v["at"]
        if k in sourceMap:
            d[sourceMap[k]] = v
        else:
            d[k] = v
    print(d)
    return JSONResponse(d)


async def homepage(request):
    return FileResponse("static/index.html")


# :bucket_seconds  = bucket size in seconds (60, 300, 3600, 86400, ...)
# :n_buckets       = how many buckets you want (e.g. 50)
bucket_avg_sql = """
WITH bucketed AS (
  SELECT
    host,
    datetime(
      (strftime('%s', ts) / :bucket_seconds) * :bucket_seconds,
      'unixepoch'
    ) AS bucket_start,
    temp,
    hum
  FROM dht
)
SELECT
  bucket_start,
  AVG(CASE WHEN host = '10.0.0.32' THEN temp END) AS in_temp,
  AVG(CASE WHEN host = '10.0.0.32' THEN hum  END) AS in_humidity,
  AVG(CASE WHEN host = '10.0.0.31' THEN temp END) AS out_temp,
  AVG(CASE WHEN host = '10.0.0.31' THEN hum  END) AS out_humidity
FROM bucketed
GROUP BY bucket_start
ORDER BY bucket_start DESC
LIMIT :n_buckets;
"""


async def bucket(request):
    period = request.path_params.get("period").strip().lower()
    num = int(request.path_params.get("num"))

    # Parse period as <number><unit>, default unit = minutes
    i = 0
    while i < len(period) and period[i].isdigit():
        i += 1
    if i == 0:
        return JSONResponse(
            {"error": "period must start with a number"}, status_code=400
        )
    value = int(period[:i])
    unit = period[i:] if i < len(period) else "minutes"

    unit_map = {
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "hour": 3600,
        "hours": 3600,
        "day": 86400,
        "days": 86400,
        "week": 604800,
        "weeks": 604800,
        "month": 2592000,  # 30 days
        "months": 2592000,  # 30 days
    }
    if unit == "":
        unit = "minutes"
    if unit not in unit_map:
        return JSONResponse({"error": f"unsupported unit '{unit}'"}, status_code=400)

    bucket_seconds = value * unit_map[unit]

    # Use read-only connection and small busy timeout for concurrency safety
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=3.0)
    try:
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        cur.execute("PRAGMA busy_timeout=3000;")
        cur.execute(
            bucket_avg_sql, {"bucket_seconds": bucket_seconds, "n_buckets": num}
        )
        rows = cur.fetchall()
    finally:
        con.close()

    result = []
    for r in rows:
        result.append(
            {
                "at": r["bucket_start"],
                "in_temp": r["in_temp"],
                "in_humidity": r["in_humidity"],
                "out_temp": r["out_temp"],
                "out_humidity": r["out_humidity"],
            }
        )
    return JSONResponse(result)


app = Starlette(
    debug=DEBUG,
    routes=[
        Route("/latest", latest, methods=["GET"]),
        Route("/bucket/{period:str}/{num:int}", bucket, methods=["GET"]),
        Mount("/static", app=StaticFiles(directory="static"), name="static"),
        Route("/", homepage, methods=["GET"]),
        Route("/index.html", homepage, methods=["GET"]),
    ],
)
