#!/usr/bin/env python
#coding: utf-8

from flask import Flask, send_from_directory

from views import player

app = Flask(__name__)
app.register_blueprint(player.bp, url_prefix="/player")

@app.route("/images/<path:path>")
def send_image(path):
  """
  jQueryのプラグインが画像を引くとき404になるのを防ぐツギハギ。
  """
  return send_from_directory("static/images", path)

@app.route("/favicon.ico")
def favicon():
  """IEが/favicon.icoを引きにくるので。"""
  return send_from_directory("static/images", "favicon.ico", mimetype="image/vnd.microsoft.icon")

if __name__ == "__main__":
    app.debug = True
    app.run("192.168.10.106", 8080)
