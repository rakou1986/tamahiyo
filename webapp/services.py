#!/usr/bin/env python
#coding: utf-8

"""
"""

import xmlrpclib

import conf

rpc = xmlrpclib.ServerProxy(conf.APISERVER)
