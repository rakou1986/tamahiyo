#!/usr/bin/env python
#coding: utf-8

import conf
from api import TamahiyoCoreAPI

import os
import signal
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import sys
import threading
import time
import xmlrpclib

day = 60 * 60 * 24

class APIService(object):
  def __init__(self):
    self.server = SimpleXMLRPCServer(conf.APISOCKNAME, requestHandler=SimpleXMLRPCRequestHandler, allow_none=True)
    self.server.register_instance(TamahiyoCoreAPI())
    self.server.register_introspection_functions() # テストの便利用、後で外す
    self.rpc = xmlrpclib.ServerProxy(conf.APISERVER)
    self.continue_ = threading.Event()
    self.continue_.set()
    self.update_at = 0
    if os.path.exists(conf.UPDATE_TIMESTAMP):
      with open(conf.UPDATE_TIMESTAMP, "r") as f:
        self.update_at = float(f.read())

  def thread_serve(self):
    self.server.serve_forever()
    print "thread_forever end"

  def thread_daily_update(self):
    while self.continue_.is_set():
      time.sleep(1)
      if day < time.time() - self.update_at:
        t_start = time.time()
        self.update_at = time.time()
        self.rpc.daily_update()
        with open(conf.UPDATE_TIMESTAMP, "w") as f:
          f.write(str(self.update_at))
        print "daily update", time.time() - t_start
    print "thread_daily_update end"

def join_threads():
  """メインスレッドで、他のスレッドの終了を待つ"""
  for t in threading.enumerate():
    if t is not threading.currentThread():
      t.join()

def exit_handler(api, signum=None, frame=None):
  api.continue_.clear()
  api.server.shutdown()
  join_threads()
  sys.exit(0)

def main():
  api = APIService()
  for signal_ in [signal.SIGINT, signal.SIGTERM]:
    signal.signal(signal_, lambda signum,frame: exit_handler(api, signum, frame))
  for thread in [threading.Thread(target=method) for method in [api.thread_serve, api.thread_daily_update]]:
    thread.start()
  while api.continue_.is_set():
    # シグナルハンドリング用のループ
    time.sleep(1)
  join_threads()

if __name__ == "__main__":
  main()
