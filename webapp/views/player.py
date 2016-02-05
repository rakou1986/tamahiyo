#!/usr/bin/env python
#coding: utf-8

from flask import render_template, Blueprint
import jinja2

bp = Blueprint("player", __name__) # 第一引数はurl_for用

@bp.route("/list/")
def list():
  return render_template("list.html")
