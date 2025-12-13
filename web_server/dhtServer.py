import json
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

PSQL_DSN = "postgresql://metrics:m3tr1cs2o25@psql.lan/metrics?sslmode=disable"

latestData = {}
sourceMap = {"10.0.0.31": "out", "10.0.0.32": "in"}


def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe("dht_sensor_measurement")


def on_message(client, userdata, msg):
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


# PostgreSQL bucketed average query
PSQL_BUCKET_SQL = """
WITH bucketed AS (
  SELECT
    host,
    to_timestamp(
      floor(extract(epoch FROM ts) / $1) * $1
    ) AS bucket_start,
    temp,
    hum
  FROM iso.dht
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
LIMIT $2;
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

    # Use PostgreSQL via psycopg/psycopg2
    try:
        try:
            import psycopg

            conn = psycopg.connect(PSQL_DSN)
            use_psycopg3 = True
        except Exception:
            import psycopg2

            conn = psycopg2.connect(PSQL_DSN)
            use_psycopg3 = False
    except Exception as e:
        return JSONResponse({"error": f"psql connection failed: {e}"}, status_code=500)

    try:
        cur = conn.cursor()
        # Execute with parameters: bucket_seconds and num
        cur.execute(PSQL_BUCKET_SQL, (bucket_seconds, num))
        rows = cur.fetchall()
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return JSONResponse({"error": f"psql query failed: {e}"}, status_code=500)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    result = []
    # Determine column indices for portability
    # Expect columns: bucket_start, in_temp, in_humidity, out_temp, out_humidity
    for r in rows:
        bucket_start = r[0]
        if hasattr(bucket_start, "strftime"):
            at_str = bucket_start.strftime("%Y-%m-%d %H:%M:%S")
        else:
            # If returned as string, keep as-is; else cast
            try:
                at_str = str(bucket_start)
            except Exception:
                at_str = None
        result.append(
            {
                "at": at_str,
                "in_temp": r[1],
                "in_humidity": r[2],
                "out_temp": r[3],
                "out_humidity": r[4],
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
