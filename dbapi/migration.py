#!/user/bin/env python
# coding: utf-8

from models import *
from services import TamahiyoCoreService
import json
import time

"""
たまひよのゲーム記録がここにある
http://tamahiyo.netgamers.jp/cgi-bin/kokko/glog.cgi

"全ての戦跡"のコピペを、tamahiyo_data.txtとする。
"""

tama = TamahiyoCoreService()

def main():
  lines = open("tamahiyo_data.txt").readlines()
  users = []
  # line.split()
  # [id_, winner1, winner2, winner3, winner4, loser1, loser2, loser3, loser4, winner_change, loser_change]
  for line in lines[1:]:
    columns = line.split()
    if len(columns) != 11:
      continue
    [users.append(u) for u in columns[1:-2]]
    users = list(set(users))
  users = [user.decode("cp932") for user in users]

  for name in users:
    user = User(name.rstrip("_"), 1600)
    if name == u"rakou1986":
      user.admin = True
    db_session.add(user)
  db_session.commit()

  len_ = len(lines[1:])
  #len_ = len(lines[-800:]) # テスト用
  now = int(time.time())
  _2_hour = 60 * 60 * 2
  for i, line in enumerate(lines[1:]):
  #for i, line in enumerate(lines[-800:]): # テスト用
    percent = int((i / float(len_)) * 100)
    print "match %d processing... %d%%" % (i+1, percent)
    #if 1000 < i: #テスト用
    #  break #テスト用
    columns = line.split()
    if len(columns) != 11: # 4v4 以外はとりあえず飛ばす
      continue
    players = columns[1:9]
    winner_change = int(columns[9])
    loser_change = int(columns[10])

    timestamp = 946652400 # 仮に2000/01/01 00:00:00とする
    active = False
    # 最近居る人だけ日数で絞り込めるように
    # 一日12戦として、最後の60日分（720戦）には別のタイムスタンプをつける
    iii = len_ - i
    if iii <= 720:
      timestamp = now - (_2_hour * (len_ - i))
      active = True
    gr = GeneralRecord(timestamp, u"#こっこたまひよ", 0, u"someone")
    gr.active = False
    db_session.add(gr)
    db_session.flush()

    for ii, player in enumerate(players):
      pr = PersonalRecord(users.index(player)+1, gr.id)
      db_session.add(pr)
      db_session.flush()
      pr.active = False
      pr.rate_at_umari = pr.user.rate
      if ii < 4:
        pr.won = True
        pr.team = 1
        pr.change_width = winner_change
        pr.determined_rate = pr.rate_at_umari + winner_change
        pr.user.won_count += 1
      else:
        pr.won = False
        pr.team = 2
        pr.change_width = loser_change
        pr.determined_rate = pr.rate_at_umari - loser_change
        pr.user.lost_count += 1
      pr.user.rate = pr.determined_rate
      pr.user.last_game_timestamp = timestamp
      if active:
        pr.user.result_last_60_days = tama._construct_result_last_60_days(pr.user, pr.won)
      db_session.flush()
      if iii in range(0, 12*60, 12):
        tama.daily_update()
  db_session.commit()

  # 連勝のやつ
  for i, user in enumerate(db_session.query(User).all()):
    print "crating streak %d" % i
    user.streak = tama._get_streak(user)
  db_session.commit()

if __name__ == "__main__":
  main()
