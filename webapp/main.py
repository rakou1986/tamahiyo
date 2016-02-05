#!/usr/bin/env python
#coding: utf-8

from flask import Flask

from views import player

app = Flask(__name__)
app.register_blueprint(player.bp, url_prefix="/player")

if __name__ == "__main__":
    app.debug = True
    app.run("192.168.10.106", 8080)
