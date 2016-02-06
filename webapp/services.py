#!/usr/bin/env python
#coding: utf-8

"""
"""

from json import loads
import xmlrpclib

import conf

rpc = xmlrpclib.ServerProxy(conf.APISERVER)

def get_all_players():
  return loads(rpc.get_all_players())
