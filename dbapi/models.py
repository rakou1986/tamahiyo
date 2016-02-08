#!/usr/bin/env python
#coding: utf-8

"""
ORMによるsqlite3データベースの定義
"""

import conf

import os
import json
from sqlalchemy import create_engine, Column, Integer, ForeignKey
from sqlalchemy.types import Unicode, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker, relation, backref

engine = create_engine(
    conf.DB_URI, encoding="utf8", echo=False, connect_args={"timeout": 20})
db_session = scoped_session(sessionmaker(bind=engine))
# exclusiveロックでトランザクションが必要な場合のtips
# db_session.execute("begin exclusive")
# db_session.commit()
Base = declarative_base()

class GeneralRecord(Base):
  """
  部屋情報。
  部屋が閉じられると、そのまま戦績になる。
  個人戦績以外の共通情報
  """
  __tablename__ = "general_records"

  id = Column(Integer, primary_key=True)
  created_at = Column(Integer, nullable=False)
  active = Column(Boolean, nullable=False)
  channel = Column(Unicode, nullable=False)
  room_number = Column(Integer, nullable=False)
  room_name = Column(Unicode)
  room_owner = Column(Unicode, nullable=False)
  game_ipaddr = Column(Unicode)
  rate_limit = Column(Integer)
  umari_at = Column(Integer)
  winner = Column(Unicode)
  completed_at = Column(Integer)
  rating_match = Column(Boolean) # 8人以外のゲームも記録するなら使う
  brokeup = Column(Boolean) # 解散したらTrue

  def __init__(self, created_at, channel, room_number, room_owner):
    self.created_at = created_at
    self.active = True
    self.channel = channel
    self.room_owner = room_owner
    self.room_number = room_number


class User(Base):
  """会員情報"""
  __tablename__ = "users"

  id = Column(Integer, primary_key=True)
  name = Column(Unicode, nullable=False, index=True, unique=True)
  rate = Column(Integer, nullable=False)
  rate_prev_30days = Column(String, nullable=False) # [rate, ...] というリスト
  allow_hurry = Column(Boolean, nullable=False)
  admin = Column(Boolean, nullable=False)
  enable = Column(Boolean, nullable=False)
  won_count = Column(Integer, nullable=False)
  lost_count = Column(Integer, nullable=False)
  streak = Column(Integer) # 連勝記録
  last_game_timestamp = Column(Integer)
  result_last_60_days = Column(String) # {timestamp: 勝(True) | 敗(False)} という辞書

  def __init__(self, name, rate):
    self.name = name
    self.rate = rate
    self.rate_prev_30days = json.dumps([rate])
    self.allow_hurry = False
    self.admin = False
    self.enable = True
    self.won_count = 0
    self.lost_count = 0
    self.result_last_60_days = "{}"


class UserAlias(Base):
  """iam＠の機能で設定できる会員の別名"""
  __tablename__ = "user_aliases"

  id = Column(Integer, primary_key=True)
  name = Column(Unicode, nullable=False, index=True, unique=True)
  
  # User:UserAlias = 1:multi
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  user = relation(User, backref=backref("user_aliases", order_by=id))

  def __init__(self, name, user_id):
    self.name = name
    self.user_id = user_id


class Session(Base):
  """会員の接続状況を記録する"""
  __tablename__ = "sessions"

  id = Column(Integer, primary_key=True)
  timestamp = Column(Integer, nullable=False)
  hostname = Column(Unicode, nullable=False)
  ipaddr = Column(Unicode)
  
  # User:Session = 1:multi
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  user = relation(User, backref=backref("sessions", order_by=id))

  def __init__(self, timestamp, hostname, ipaddr, user_id):
    self.timestamp = timestamp
    self.hostname = hostname
    self.ipaddr = ipaddr
    self.user_id = user_id


class PersonalRecord(Base):
  """部屋への参加状況。そのまま個人戦績になる。
  GeneralRecord（部屋情報兼戦績）とUserを多対多にする中間テーブルを兼ねる
  """
  __tablename__ = "personal_records"

  id = Column(Integer, primary_key=True)
  active = Column(Boolean, nullable=False)
  leaved = Column(Boolean)
  kicked = Column(Boolean)
  team = Column(Integer)
  won = Column(Boolean)
  change_width = Column(Integer)  # レートの変動量
  determined_rate = Column(Integer) # 変動後のレート。推移グラフに使える
  rate_at_umari = Column(Integer) # 部屋が埋まりチームを決めた当時のレート。勝敗のレート計算に使う

  # User:PersonalRecord = 1:multi
  user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
  user = relation(User, backref=backref("personal_records", order_by=id))

  # GeneralRecord:PersonalRecord = 1:multi
  general_record_id = Column(Integer, ForeignKey("general_records.id"), nullable=False)
  general_record = relation(GeneralRecord, backref=backref("personal_records", order_by=id))

  def __init__(self, user_id, general_record_id):
    self.active = True
    self.leaved = False
    self.kicked = False
    self.user_id = user_id
    self.general_record_id = general_record_id


class RoomNumberPool(Base):
  """部屋番号の振り出し管理
  配列の永続化のために1レコード使うだけ"""

  __tablename__ = "room_number_pool"

  id = Column(Integer, primary_key=True)
  jsonstring = Column(String, nullable=False)

  def __init__(self, jsonstring):
    self.jsonstring = jsonstring
