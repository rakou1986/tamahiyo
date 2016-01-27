#!/usr/bin/env python
#coding: utf-8

from api import TamahiyoCoreAPI
from models import (db_session, GeneralRecord, User,
  UserAlias, PersonalRecord, Session, RoomNumberPool)

import random
from json import dumps, loads
import time

tama = TamahiyoCoreAPI()

def users_random_pop(users):
  user = users.pop(random.choice(range(len(users))))
  return user, users

def make_room(users):
  owner, users = users_random_pop(users)
  gr = GeneralRecord(int(time.time()), u"#たまひよ", tama._pick_room_number(), owner.name)
  gr.game_ipaddr = u"127.0.0.1"
  db_session.add(gr)
  db_session.flush()
  pr = PersonalRecord(owner.id, gr.id)
  db_session.add(pr)
  db_session.flush()
  return gr.id, owner, users

def join_room1(gr_id, users):
  user, users = users_random_pop(users)
  pr = PersonalRecord(user.id, gr_id)
  db_session.add(pr)
  db_session.flush()
  return users

def join_room2(gr_id, users):
  user, users = users_random_pop(users)
  args = {
      "caller": user.name,
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
  }
  tama.join_room(dumps(args))
  return users

def save_result(owner):
  args = {
      "caller": owner.name,
      "channel": u"#たまひよ",
      "won": random.choice([True, False]),
  }
  tama.save_result(dumps(args))

grs = db_session.query(GeneralRecord).all()
grs_len_start = len(grs)

for i in range(10000):
  print "***************", i
  users = db_session.query(User).all()
  gr_id, owner, users = make_room(users)
  for ii in range(6):
    users = join_room1(gr_id, users)
  users = join_room2(gr_id, users)
  save_result(owner)

grs = db_session.query(GeneralRecord).filter(grs_len_start < GeneralRecord.id).all()

changes = []
for gr in grs:
  for pr in gr.personal_records:
    if pr.team == 1:
      team1_change = pr.change_width
    if pr.team == 2:
      team2_change = pr.change_width
  changes.append(team1_change)
  changes.append(team2_change)

x = []
y = []
for i in range(30):
  x.append(i)
  y.append(changes.count(i))

print "X =", x
print "Y =", y
