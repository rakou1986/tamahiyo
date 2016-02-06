#!/usr/bin/env python
#coding: utf-8

from flask import render_template, Blueprint

import services # webapp/services.py

bp = Blueprint("player", __name__) # 第一引数はurl_for用

@bp.route("/list/")
def list():
  players = services.get_all_players()
  return render_template("player_list.html", players=players)
