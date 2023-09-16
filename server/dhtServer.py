import json
import sqlite3
from datetime import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

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
  date_time = now.strftime("%m/%d/%Y, %H:%M:%S")
  latestData[d['id']] = {'temp': d['temp'], 'hum': d['hum'], 'at': date_time}

  with con:
    con.execute("insert into dht (source, temp, hum) values (?, ?, ?)", (d['id'], d['temp'], d['hum']))

  return JSONResponse({'success': True})


async def latest(request):
  #return latestData but lookup id from sourceMap
  d = {}
  for k, v in latestData.items():
    v['source'] = k
    if k in sourceMap:
      d[sourceMap[k]] = v
    else:
      d[k] = v
  return JSONResponse(d)


app = Starlette(debug=True, routes=[
  Route('/dht', dht, methods=['POST']),
  Route('/latest', latest, methods=['GET'])
])

