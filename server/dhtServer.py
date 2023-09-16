import urllib
import json
from bottle import route, run, post, request
import sqlite3

con = sqlite3.connect("/home/andre/dhtServer/dht.db")

with con:
  con.execute("create table if not exists dht (id integer primary key, source integer, temp real, hum real, ts timestamp default current_timestamp)")

with con:
  con.execute("create index if not exists dht_source on dht (source)")

@post('/dht')
def dht():
    d = json.load(request.body)
    print("source: %d, temp: %3.1f, hum: %3.1f" %(d['id'], d['temp'], d['hum']))

    with con:
      con.execute("insert into dht (source, temp, hum) values (?, ?, ?)", (d['id'], d['temp'], d['hum']))

    #body1 = request.body.read();
    #body = urllib.unquote(body1).decode('utf8')
    #print(body)
    return "logged.."

run(host='0.0.0.0', port=80, debug=True)

