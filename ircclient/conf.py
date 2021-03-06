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

IRCSERVER = ("irc.ircnet.ne.jp", 6667)
NICKNAME = "_tamachan"
ENCODING = "iso-2022-jp"
CHANNELS = [
  u"", #  u"#room_name"
  ]
ANNOUNCE_INTERVAL = 60 * 5
USAGE_URL = u"http://ここに説明書のURLを書く"

APISERVER = "http://127.0.0.1:12000"

POLL_INTERVAL = 0.001
