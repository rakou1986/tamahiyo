#!/user/bin/env python
# coding: utf-8

from models import *
import json

"""
たまひよのゲーム記録がここにある
http://tamahiyo.netgamers.jp/cgi-bin/kokko/glog.cgi

"全ての戦跡"のコピペを、tamahiyo_data.txtとする。
"""

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
  for i, line in enumerate(lines[1:]):
    percent = int((i / float(len_)) * 100)
    print "match %d processing... %d%%" % (i+1, percent)
    #テスト回し用
    #if 5 < i:
    #  break
    columns = line.split()
    if len(columns) != 11: # 4v4 以外はとりあえず飛ばす
      continue
    players = columns[1:9]
    winner_change = int(columns[9])
    loser_change = int(columns[10])

    tmptime = 946652400 # 仮に2000/01/01 00:00:00とする
    gr = GeneralRecord(tmptime, u"#こっこたまひよ", 0, u"someone")
    gr.active = False
    db_session.add(gr)
    db_session.flush()

    for i, player in enumerate(players):
      pr = PersonalRecord(users.index(player)+1, gr.id)
      db_session.add(pr)
      db_session.flush()
      pr.active = False
      pr.rate_at_umari = pr.user.rate
      if i < 4:
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
      db_session.flush()
  db_session.commit()

if __name__ == "__main__":
  main()
