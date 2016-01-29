#!/usr/bin/env python
#coding: utf-8

# ローカルの変更を無視
# git update-index --assume-unchanged
# 元に戻す
# git update-index --no-assume-unchanged
#
# 無視ファイルの探し方
# git ls-files -v
# で、行頭が小文字 h となっているもの

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
