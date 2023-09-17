import json
import sqlite3
from datetime import datetime

from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse
from starlette.routing import Route
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.config import Config

latestData = {}
sourceMap = {202: 'isopod 1'}

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
  Route('/latest', latest, methods=['GET']),
  Mount('/static', app=StaticFiles(directory='static'), name="static"),
  Route('/', homepage, methods=['GET']),
  Route('/index.html', homepage, methods=['GET']),
])

