#!/usr/bin/env python
#coding: utf-8

"""

"""

import conf

import select
import signal
import socket
import sys
import threading
import time

import services

bufsize = 32768
irc_proxy_thread = ("127.0.0.1", 12010)
service_thread = ("127.0.0.1", 12011)

class Tamachan(object):
  def __init__(self):
    self.continue_ = threading.Event()
    self.continue_.set() # is_set() == True
    self.announce_timer = time.time()

  def _select(self, socket_, timeout=0):
      try:
        r, w, e = select.select([socket_], [], [], timeout)
      except socket.error:
        self.continue_.clear()
        return None
      if r:
        return r[0]
      else:
        return None

  def _send(self, socket_, msg, dst=None):
    try:
      if dst:
        socket_.sendto(msg, dst)
      else:
        socket_.send(msg)
    except socket.error:
      self.continue_.clear()

  # :rakou1986!~rakou1986@113x37x106x22.ap113.ftth.ucom.ne.jp PRIVMSG #rakou$NIt20 :naisenn?
  def _announce(self, sock_ipc):
    if conf.ANNOUNCE_INTERVAL < (time.time() - self.announce_timer):
      for channel in conf.CHANNELS:
        msg = ":%s!~%s@localhost PRIVMSG %s :naisen?" % (
            conf.NICKNAME,
            conf.NICKNAME,
            channel.encode(conf.ENCODING))
        self._send(sock_ipc, msg, service_thread)
      self.announce_timer = time.time()

  def irc_proxy_thread(self):
    sock_ipc = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock_ipc.bind(irc_proxy_thread)
    sock_ipc.setblocking(0)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
      sock.connect(conf.IRCSERVER)
      sock.setblocking(0)
      sock.send("NICK %s\r\n" % conf.NICKNAME)
      sock.send("USER %s 0 * %s\r\n" % (conf.NICKNAME, conf.NICKNAME))
      for channel in conf.CHANNELS:
        sock.send("JOIN %s\r\n" % channel.encode(conf.ENCODING))
      if not self._select(sock, 120):
        print "connect timeout"
        self.continue_.clear()
      msg = sock.recv(bufsize)
      print msg
      pong_host, tail = msg[1:].split(" ", 1)
    except socket.error:
      print "socket.error"
      self.continue_.clear() # is_set() == True
    except Exception:
      print "Exception"
      self.continue_.clear() # is_set() == True
    while self.continue_.is_set():
      if self._select(sock, conf.POLL_INTERVAL):
        msg = sock.recv(bufsize)
        if msg == "":
          print self.continue_.is_set()
          self.continue_.clear()
          print self.continue_.is_set()
          print "eof received"
          continue
        else:
          print [msg]
          if "PING" in msg:
            self._send(sock, "PONG %s\r\n" % pong_host)
          if "ERROR" in msg:
            if "Ping timeout" in msg:
              self.continue_.clear()
              print "ping timeout"
              continue
          self._send(sock_ipc, msg, service_thread)
      if self._select(sock_ipc, conf.POLL_INTERVAL):
        msg = sock_ipc.recv(bufsize)
        self._send(sock, msg)
        print [msg]
      self._announce(sock_ipc)
    self._send(sock, "QUIT\r\n")
    sock.close()
    sock_ipc.close()
    print "irc_proxy_thread end"

  def service_thread(self):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(service_thread)
    sock.setblocking(0)
    while self.continue_.is_set():
      if self._select(sock, conf.POLL_INTERVAL):
        msg = sock.recv(bufsize)
        for s in msg.strip().split("\r\n"):
          msg = services.facade(s)
          if msg:
            self._send(sock, msg, irc_proxy_thread)
    sock.close()
    print "service_thread end"

def join_threads():
  """メインスレッドで、他のスレッドの終了を待つ"""
  for t in threading.enumerate():
    if t is not threading.currentThread():
      t.join()

def exit_handler(tamachan, signum=None, frame=None):
  tamachan.continue_.clear()
  join_threads()
  sys.exit(0)

def tamachan_life_cycle():
  tamachan = Tamachan()
  for signal_ in [signal.SIGINT, signal.SIGTERM]:
    signal.signal(signal_, lambda signum,frame: exit_handler(tamachan, signum, frame))
  for thread in [threading.Thread(target=method) for method in [tamachan.service_thread, tamachan.irc_proxy_thread]]:
    thread.start()
  while tamachan.continue_.is_set():
    # シグナルハンドリング用のループ
    time.sleep(1)
  join_threads()

def main():
  while True:
    tamachan_life_cycle()
    time.sleep(60) # 落ちたら1分後に再接続

if __name__ == "__main__":
  main()
