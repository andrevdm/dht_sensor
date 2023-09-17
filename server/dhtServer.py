import json
import sqlite3
from datetime import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.config import Config

con = sqlite3.connect("/home/andre/dhtServer/dht.db")

with con:
  con.execute("create table if not exists dht (id integer primary key, source integer, temp real, hum real, ts timestamp default current_timestamp)")

with con:
  con.execute("create index if not exists dht_source on dht (source)")

latestData = {}
sourceMap = {202: 'isopod 1'}

async def dht(request):
  d = await request.json()
  #print("source: %d, temp: %3.1f, hum: %3.1f" %(d['id'], d['temp'], d['hum']))
  now = datetime.now()
  date_time = now.strftime("%Y/%m/%d, %H:%M:%S")
  latestData[d['id']] = {'temp': d['temp'], 'hum': d['hum'], 'at': date_time}

  with con:
    con.execute("insert into dht (source, temp, hum) values (?, ?, ?)", (d['id'], d['temp'], d['hum']))

  return JSONResponse({'success': True})


async def latest(request):
  #return latestData but lookup id from sourceMap
  d = {}
  for k, v in latestData.items():
    v['source'] = k
    v['at'] = v['at']
    if k in sourceMap:
      d[sourceMap[k]] = v
    else:
      d[k] = v
  print(d)
  return JSONResponse(d)

async def homepage(request):
  return FileResponse('static/index.html')

# Config will be read from environment variables and/or ".env" files.
config = Config(".env")
DEBUG = config('DEBUG', cast=bool, default=False)

app = Starlette(debug=DEBUG, routes=[
  Route('/dht', dht, methods=['POST']),
  Route('/latest', latest, methods=['GET']),
  Mount('/static', app=StaticFiles(directory='static'), name="static"),
  Route('/', homepage, methods=['GET']),
  Route('/index.html', homepage, methods=['GET']),
])

