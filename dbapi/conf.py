#!/usr/bin/env python
#coding: utf-8

from os.path import abspath, dirname, join
import sys

ROOT = dirname(abspath(__file__)) # conf.pyのあるディレクトリの絶対パス
sys.path.insert(0, join(ROOT, "lib/python2.7"))

DB_URI = "".join(["sqlite:///", join(ROOT, "tamahiyo.sqlite3")])
TEAM1 = 1
TEAM2 = 2

APISOCKNAME = ("127.0.0.1", 12000)
APISERVER = "http://127.0.0.1:12000"

UPDATE_TIMESTAMP = "update_timestamp.tmp"
