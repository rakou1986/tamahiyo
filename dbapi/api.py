#!/usr/bin/env python
#coding: utf-8

"""シングルスレッドでいい"""

import conf

import datetime
import math
import socket
import time
from json import dumps, loads
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound

from models import (db_session, GeneralRecord, User,
  UserAlias, PersonalRecord, Session, RoomNumberPool)

class TamahiyoCoreHelper(object):
  def __init__(self):
    self._initialize_rnp()

  def _initialize_rnp(self):
    rnp = self._get_rnp()
    if rnp is None:
      rnp = RoomNumberPool(dumps(range(1,101)))
      db_session.add(rnp)
      db_session.commit()

  def _get_rnp(self):
    q = db_session.query(RoomNumberPool
      ).filter(RoomNumberPool.id==1
      )
    try:
      return q.one()
    except NoResultFound:
      return None

  def _whoami(
        self, name, alias_contain=True, forward_match=False,
        partial_match=False, backward_match=False, one=False):
    if forward_match or partial_match or backward_match:
      if forward_match: base = u"%s%%"
      if partial_match: base = u"%%%s%%"
      if backward_match: base = u"%%%s"
      users = db_session.query(User
          ).filter(User.enable==True
          ).filter(User.name.like(base % self._rstrip_underscore(name))
          ).all()
      if alias_contain:
        aliases = db_session.query(UserAlias
            ).filter(UserAlias.name.like(base % name)
            ).all()
        for alias in aliases:
          if alias.user.enable and (alias.user not in users):
            users.append(alias.user)
      if one:
        if len(users) == 1:
          return users[0]
        else:
          return None
      else:
        return users if users else None
    else:
      try:
        return db_session.query(User
            ).filter(User.name==self._rstrip_underscore(name)
            ).filter(User.enable==True
            ).one()
      except NoResultFound:
        pass
      if alias_contain:
        try:
          alias = db_session.query(UserAlias).filter(UserAlias.name==name).one()
          return alias.user if alias.user.enable else None
        except NoResultFound:
          pass
      return None

  def _pick_room_number(self):
    rnp = self._get_rnp()
    numbers = sorted(loads(rnp.jsonstring))
    room_number = numbers.pop(0)
    rnp.jsonstring = dumps(numbers)
    db_session.flush()
    return room_number

  def _acquire_room_number(self, number):
    rnp = self._get_rnp()
    numbers = sorted(loads(rnp.jsonstring))
    numbers.append(number)
    rnp.jsonstring = dumps(numbers)
    db_session.flush()

  def _get_active_pr(self, user):
    q = db_session.query(PersonalRecord
      ).filter(PersonalRecord.user_id == user.id
      ).filter(PersonalRecord.active == True
      )
    try:
      return q.one()
    except NoResultFound:
      return None

  def _get_dst_gr(self, channel, room_number):
    q = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.channel==channel)
    try:
      return q.one()
    except NoResultFound:
      pass
    except MultipleResultsFound:
      pass
    if room_number:
      q = q.filter(GeneralRecord.room_number==room_number)
    try:
      return q.one()
    except NoResultFound:
      return None
    except MultipleResultsFound:
      return None

  def _join_to_room(self, user, general_record):
    pr = PersonalRecord(user.id, general_record.id)
    db_session.add(pr)
    db_session.flush()
    
  def _get_inside_member_prs(self, general_record):
    members = []
    for pr in general_record.personal_records:
      if pr.active:
        members.append(pr)
    return members

  # 8人の分けならこれでいい。任意の人数版がだめなときの予備
  # def _team_assign(self, general_record):
  #   members = self._get_inside_member_prs(general_record=general_record)
  #   prs = [pr for pr in members]
  #   rates = [pr.user.rate for pr in members]
  #   ideal = sum(rates) / 2.0

  #   idx_and_IdealDegree = []
  #   for i in range(8**4):
  #     four_idx = [int(s) for s in "%04o" % i]
  #     idx_one_by_one = list(set(four_idx))
  #     if len(idx_one_by_one) == 4:
  #       ideal_degree = abs(ideal - sum([rates[idx] for idx in idx_one_by_one]))
  #       idx_and_IdealDegree.append((idx_one_by_one, ideal_degree))
  #   idx_and_IdealDegree.sort(key=lambda element: element[1])
  #   most_ideally_combination_idx = idx_and_IdealDegree[0][0]
  #   mici = sorted(most_ideally_combination_idx, reverse=True)
  #   team1 = [prs.pop(idx) for idx in mici]
  #   team2 = prs
  #   for pr in team1:
  #     pr.team = conf.TEAM1
  #   for pr in team2:
  #     pr.team = conf.TEAM2

  # 任意の人数をチーム分け
  def _team_assign(self, general_record):

    # 10進数（自然数）をn進数に変換する関数。拾い物。動作確認済み
    def convert_natural_radix_10_to_n(x, n):
      if x < 0: return None
      if n < 2 or 16 < n: return None
      if x == 0: return 0
      nchar = '0123456789ABCDEF'
      digit = 0
      result = ''
      while x > 0:
        result = nchar[x % n] + result
        x = x / n
      return result

    prs = self._get_inside_member_prs(general_record=general_record)
    pop = len(prs)
    num_of_digits = pop - int(pop / 2.0) #奇数の場合人数の多い方を理想レートに近づける
    rates = [pr.user.rate for pr in prs]
    ideal = sum(rates) / 2.0 # 総和の1/2が理想とする
    idx_and_IdealDegree = [] # 組み合わせごとの理想度をメモするリスト

    # pop進数のチーム人数桁まで考えればよい
    for i in range(pop**num_of_digits):
      some_idx = [int(s) for s in str(convert_natural_radix_10_to_n(i, pop)).rjust(num_of_digits, "0")]
      # そのうち同じ人が同じチームに二度以上入る組み合わせを取り除く
      idx_one_by_one = list(set(some_idx))
      if len(idx_one_by_one) == num_of_digits:
        # 理想との差を理想度とする
        ideal_degree = abs(ideal - sum([rates[idx] for idx in idx_one_by_one]))
        idx_and_IdealDegree.append((idx_one_by_one, ideal_degree))
    # 理想との差が少ない順にソート
    idx_and_IdealDegree.sort(key=lambda element: element[1])
    most_ideally_combination_idx = idx_and_IdealDegree[0][0]
    # pop()で要素を取り出すとindexが切り詰められるので、末尾からpop()する
    mici = sorted(most_ideally_combination_idx, reverse=True)
    team1 = [prs.pop(idx) for idx in mici]
    team2 = prs

    for pr in team1:
      pr.team = conf.TEAM1
    for pr in team2:
      pr.team = conf.TEAM2

  def _is_room_owner(self, channel, caller):
    user = self._whoami(caller)
    if user is None:
      return False
    pr = self._get_active_pr(user)
    if pr is None:
      return False
    gr = pr.general_record
    if (gr.room_owner == user.name) and (gr.channel == channel):
      return pr
    return False
  
  def _execute_breakup(self, gr):
    gr.active = False
    gr.brokeup = True
    members = []
    for pr in gr.personal_records:
      if pr.active:
        pr.active = False
        members.append(pr)
    db_session.flush()
    self._acquire_room_number(gr.room_number)
    return members

  def _construct_member_info(self, pr):
    return {
        "name": pr.user.name,
        "rate": pr.user.rate,
        "team": pr.team,
        "won": pr.won,
        "change_width": pr.change_width,
        "determined_rate": pr.determined_rate,
        }
    
  def _construct_room_info(self, gr, user=None):
    caller = None
    if user:
      caller = user.name
    members = []
    for pr in gr.personal_records:
      if pr.active:
        members.append(self._construct_member_info(pr))
    return {
      "created_at": gr.created_at,
      "channel": gr.channel,
      "room_name": gr.room_name,
      "room_owner": gr.room_owner,
      "game_ipaddr": gr.game_ipaddr,
      "room_number": gr.room_number,
      "rate_limit": gr.rate_limit,
      "umari_at": gr.umari_at,
      "winner": gr.winner,
      "completed_at": gr.completed_at,
      "rating_match": gr.rating_match,
      "brokeup": gr.brokeup,
      "members": members,
      "caller": caller,
      }

  def _rollback_result(self, gr):
    members = db_session.query(PersonalRecord
      ).filter(PersonalRecord.general_record_id == gr.id
      ).filter(PersonalRecord.won != None
      ).all()
    for pr in members:
      if pr.won:
        pr.user.won_count -= 1
      else:
        pr.user.lost_count -= 1
      if gr.rating_match:
        pr.user.rate = pr.user.rate - (pr.change_width if pr.won else -pr.change_width)
    db_session.flush()
    return members

  def _save_result(self, owner_pr, won, rollback=False):
    gr = owner_pr.general_record
    enemy_team = conf.TEAM2 if conf.TEAM1 == owner_pr.team else conf.TEAM1
    gr.winner = owner_pr.team if won else enemy_team
    gr.completed_at = int(time.time())
    gr.active = False
    db_session.flush()
    self._acquire_room_number(gr.room_number)
    if rollback:
      members = self._rollback_result(gr)
    else:
      members = []
      for pr in gr.personal_records:
        if pr.active:
          members.append(pr)
    for pr in members:
      pr.won = True if pr.team == gr.winner else False
      pr.active = False
      if pr.won:
        pr.user.won_count += 1
      else:
        pr.user.lost_count += 1
      if gr.rating_match:
        pr.change_width = self._calc_change_width(pr)
        pr.determined_rate = pr.user.rate + (pr.change_width if pr.won else -pr.change_width)
    for pr in members:
      if pr.determined_rate is not None:
        pr.user.rate = pr.determined_rate
    db_session.flush()

  def _calc_change_width(self, pr):
    # イロレーティングを基本にしたレートシステム
    K = 26
    Ra, Rb = 0, 0
    for pr_ in pr.general_record.personal_records:
      if pr.team == pr_.team:
        Ra += pr_.user.rate
      else:
        Rb += pr_.user.rate
    Ea = 1.0 / (1 + (10**((Rb - Ra) / 400.0)))
    change_width = int(K * (int(pr.won) - Ea))
    if pr.won is False:
      change_width -= 1
    print pr.user.name, pr.won, Ra, Rb, Ea, abs(change_width)
    return abs(change_width)

  def _save_session(self, hostname, user):
    try:
      ipaddr = unicode(socket.gethostbyname(hostname))
    except socket.gaierror: # DNSが引けないとかネット切断とか
      ipaddr = None
    db_session.add(Session(int(time.time()), hostname, ipaddr, user.id))
    db_session.flush()

  def _get_std_score(self, user, rates):
    # 偏差値は平均との差を10倍して標準偏差で割って50足す
    # 00:50 (aikuchi) 標準偏差は、各プレイヤーのレートの平均との差を２乗して
    # 00:50 (aikuchi) 合計したもののルート
    # 00:50 (aikuchi) これも簡単
    # 00:51 (rakou1986_ffxi) そう言われると簡単ｗ
    # 00:51 (rakou1986_ffxi) ありがとう
    # 00:52 (aikuchi) }a,
    # 00:52 (aikuchi) 1/N忘れた
    # 00:52 (aikuchi) プレイヤー数で割ったあとにルートですね
    # 00:54 (rakou1986_ffxi) じゃあ
    # 00:54 (ninneko___) 結局全機能を把握できていない
    # 00:55 (aikuchi) ゴミみたいな機能もあるし、ごっそり削ってもらってもOK
    # 00:55 (aikuchi) あとからでも機能は追加できますしね
    # 00:55 (ninneko___) いったんゲームに参加できればいいくらいのほうがいいな
    # 00:55 (rakou1986_ffxi) 標準偏差は、平均レートとの差の2乗、全員分の平均　のルート
    n = len(rates)
    if n == 1:
      return 0.0
    avg = sum(rates) / float(n)
    sigma_x = math.sqrt(sum([(rate - avg)**2 for rate in rates]) / float(n))
    std_score = (((user.rate - avg) * 10) / sigma_x) + 50
    return std_score

  def _rstrip_underscore(self, s):
    return s.rstrip("_")


class TamahiyoCoreAPI(TamahiyoCoreHelper):
  def __init__(self):
    super(TamahiyoCoreAPI, self).__init__()

  def daily_update(self):
    # プレイヤーそれぞれのレートを毎日プロットし、31日以上前のものは消す
    for user in db_session.query(User).all():
      rate_prev_30days = loads(user.rate_prev_30days)
      rate_prev_30days.append(user.rate)
      if 30 < len(rate_prev_30days):
        rate_prev_30days.pop(0)
      user.rate_prev_30days = dumps(rate_prev_30days)
    db_session.commit()

  def add_user(self, json):
    """たまひよ会員新規登録"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"], alias_contain=False)
    if (user is None) or (not user.admin):
      return dumps((False,))
    db_session.add(User(self._rstrip_underscore(args["newcomer"]), args["rate"]))
    try:
      db_session.commit()
    except IntegrityError:
      db_session.rollback()
      return dumps((False,))
    return dumps((True,))

  def iam(self, json): # Web版のみにしないとまずい気が
    """別名登録"""
    args = loads(json)
    print args
    user = self._whoami(args["alias"], alias_contain=False)
    if user is not None:
      return dumps((False,))
    user = self._whoami(args["original_name"], alias_contain=False)
    if user is None:
      return dumps((False,))
    db_session.add(UserAlias(args["alias"], user.id))
    try:
      db_session.flush()
    except IntegrityError:
      db_session.rollback()
      return dumps((False,))
    self._save_session(args["hostname"], user)
    db_session.commit()
    return dumps((True,))

  def delete_alias(self, json):
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    try:
      alias = db_session.query(UserAlias
          ).filter(UserAlias.name==args["alias"]
          ).one()
    except:
      return dumps((False,))
    if (alias.user.id != user.id) and (not user.admin):
      return dumps((False,))
    db_session.delete(alias)
    db_session.commit()
    return dumps((True,))

  def make_room(self, json):
    """部屋作成、更新"""
    args = loads(json)
    print args

    # 登録されたuserでなければならない
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))

    # ホスト以外はどの部屋にも入っていない状態でなければ使えない
    owner_pr = self._is_room_owner(args["channel"], args["caller"])
    pr = self._get_active_pr(user)
    if bool(pr) and (not bool(owner_pr)):
      return dumps((False,))

    if owner_pr:
      gr = owner_pr.general_record
      gr.room_name = args["room_name"]
      gr.rate_limit = args["rate_limit"]
      db_session.flush()
    else:
      gr = GeneralRecord(int(time.time()), args["channel"], self._pick_room_number(), user.name)
      gr.room_name = args["room_name"]
      gr.rate_limit = args["rate_limit"]
      gr.game_ipaddr = args["ip_addr"]
      db_session.add(gr)
      db_session.flush()
      self._join_to_room(user, gr)
    self._save_session(args["hostname"], user)
    db_session.commit()
    return dumps((True, self._construct_room_info(gr, user)))

  def join_room(self, json):
    """入室"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    if self._get_active_pr(user):
      return dumps((False,))
    gr = self._get_dst_gr(args["channel"], args["room_number"])
    if gr is None:
      return dumps((False,))
    if gr.umari_at:
      return dumps((False,))
    if gr.umari_at is not None:
      return dumps((False,))
    # TODO: レート制限のテスト
    if gr.rate_limit:
      if gr.rate_limit < user.rate:
        return dumps((False,))
    self._join_to_room(user, gr)
    db_session.commit()

    members = self._get_inside_member_prs(general_record=gr)
    print "******"
    print len(members)
    if len(members) == 8:
      gr.umari_at = int(time.time())
      gr.rating_match = True
      db_session.flush()
      self._team_assign(gr)
      db_session.flush()
      print [gr.umari_at, gr.rating_match]
    self._save_session(args["hostname"], user)
    db_session.commit()
    return dumps((True, self._construct_room_info(gr, user)))

  def umari_force(self, json):
    """＄うまりコマンド"""
    args = loads(json)
    print args
    pr = self._is_room_owner(args["channel"], args["caller"])
    if pr is False:
      return dumps((False,))
    gr = pr.general_record
    if gr.umari_at is not None:
      return dumps((False,))
    members = self._get_inside_member_prs(general_record=gr)
    if len(members) == 1:
      return dumps((False,))
    gr.umari_at = int(time.time())
    gr.rating_match = False
    self._team_assign(gr)
    db_session.commit()
    return dumps((True, self._construct_room_info(gr, pr.user)))

  def leave_room(self, json):
    """退室。ホストが抜けたら解散"""
    args = loads(json)
    print args
    pr = self._is_room_owner(args["channel"], args["caller"])
    if pr:
      members = self._execute_breakup(pr.general_record)
    else:
      user = self._whoami(args["caller"])
      if user is None:
        return dumps((False,))
      pr = self._get_active_pr(user)
      if pr is None:
        return dumps((False,))
      if pr.general_record.channel != args["channel"]:
        return dumps((False,))
      pr.active = False
      pr.leaved = True
    pr.general_record.umari_at = None
    pr.general_record.rating_match = None
    db_session.commit()
    returns = self._construct_room_info(pr.general_record, pr.user)
    if pr.general_record.brokeup:
      returns.update({"members": [self._construct_member_info(pr) for pr in members]})
    return dumps((True, returns))

  def kick_out(self, json):
    """kick@nameコマンド"""
    args = loads(json)
    print args
    target_user = self._whoami(args["target_name"])
    if target_user is None:
      return dumps((False,))
    target_pr = self._get_active_pr(target_user)
    if target_pr is None:
      return dumps((False,))
    pr = self._is_room_owner(args["channel"], args["caller"])
    if not pr:
      return dumps((False,))
    if pr.user.id == target_pr.user.id:
      return dumps((False,))
    if pr.general_record.id == target_pr.general_record.id:
      target_pr.active = False
      target_pr.kicked = True
      target_pr.general_record.umari_at = None
      target_pr.general_record.rating_match = None
      db_session.commit()
    returns = self._construct_room_info(pr.general_record, pr.user)
    returns.update({"kicked_out": target_user.name})
    return dumps((True, returns))

  def breakup(self, json):
    """解散、強制解散"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    pr = self._is_room_owner(args["channel"], args["caller"])
    if (not pr) and (not args["force"]):
      return dumps((False,))
    if (not pr) and args["force"]:
      q = db_session.query(GeneralRecord
        ).filter(GeneralRecord.active==True
        ).filter(GeneralRecord.room_number==args["room_number"]
        ).filter(GeneralRecord.channel==args["channel"])
      try:
        gr = q.one()
      except NoResultFound:
        return dumps((False,))
    else:
      gr = pr.general_record
    members = self._execute_breakup(gr)
    returns = self._construct_room_info(gr, user)
    returns.update({"members": [self._construct_member_info(pr) for pr in members]})
    db_session.commit()
    return dumps((True, returns))

  def save_result(self, json):
    """勝敗をつける"""
    args = loads(json)
    print args
    pr = self._is_room_owner(args["channel"], args["caller"])
    if pr is False:
      return dumps((False,))
    gr = pr.general_record
    self._save_result(pr, args["won"])
    print [pr.active for pr in gr.personal_records]
    returns = self._construct_room_info(gr, pr.user)
    returns.update({
      "members": [self._construct_member_info(member) for member in gr.personal_records],
      })
    db_session.commit()
    return dumps((True, returns))

  def fix_prev_result(self, json):
    """直前の勝敗をつけ直す"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    try:
      # UserのPersonalRecordのうち最新のレコードを取得
      pr_id = db_session.query(
        func.max(PersonalRecord.id)
        ).correlate(PersonalRecord
        ).filter(PersonalRecord.user_id==user.id).one()[0]
      pr = db_session.query(PersonalRecord
        ).filter(PersonalRecord.id==pr_id).one()
    except NoResultFound:
      return dumps((False,))
    if (pr.general_record.room_owner != pr.user.name) or (pr.general_record.completed_at is None):
      return dumps((False,))
    self._save_result(pr, args["won"], rollback=True)
    gr = pr.general_record
    members = []
    for member in gr.personal_records:
      if member.won is not None:
        members.append(member)
    returns = self._construct_room_info(gr, pr.user)
    returns.update({"members": [self._construct_member_info(member) for member in members]})
    return dumps((True, returns))

  def change_game_ipaddr(self, json):
    """代理"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    pr = self._get_active_pr(user)
    if pr is None:
      return dumps((False,))
    gr = pr.general_record
    if gr.channel != args["channel"]:
      return dumps((False,))
    gr.game_ipaddr = args["ip_addr"]
    db_session.commit()
    return dumps((True, self._construct_room_info(pr.general_record, user)))

  def get_active_rooms(self, json):
    """内戦？コマンド"""
    args = loads(json)
    print args
    rooms = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.channel==args["channel"]
      ).order_by(GeneralRecord.room_number
      ).all()
    return dumps((True, [self._construct_room_info(gr) for gr in rooms]))

  def get_room_info(self, json):
    # TODO: test
    """参加者"""
    args = loads(json)
    print args
    gr = self._get_dst_gr(args["channel"], args["room_number"])
    if gr is None:
      return dumps((False,))
    return dumps((True, self._construct_room_info(gr)))

  def get_hurried_members(self, json):
    args = loads(json)
    print args
    users = db_session.query(User
        ).filter(User.allow_hurry==True
        ).filter(User.rate <= args["rate"]
        ).all()
    names = []
    for user in users:
        names.append(user.name)
    return dumps((True, names))

  def allow_hurry(self, json):
    args = loads(json)
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    user.allow_hurry = True
    db_session.commit()
    return dumps((True,))

  def disallow_hurry(self, json):
    args = loads(json)
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    user.allow_hurry = False
    db_session.commit()
    return dumps((True,))

  # 07:11 (koujan) rakou1986 719位 レート:440(先月比: 3) 戦績:136勝172敗 (勝率: 44.15%)
  def get_user_info(self, json):
    args = loads(json)
    print args
    users = self._whoami(args["username"], forward_match=True)
    if users is None:
      return dumps((False,))

    all_users = db_session.query(User).order_by(User.rate).all()
    all_users.reverse()
    user_infos = []
    for user in users:
      user_infos.append({
          "name": user.name,
          "rate_current": user.rate,
          "rate_prev_30days": loads(user.rate_prev_30days)[0],
          "won_count": user.won_count,
          "lost_count": user.lost_count,
          "ranking": all_users.index(user) + 1,
          "std_score": self._get_std_score(user, [u.rate for u in all_users])})
    return dumps((True, user_infos))

  def get_kdata(self, json):
    """leftsのrightsに対する勝敗数"""
    args = loads(json)
    print args
    lefts = []
    rights = []
    for name in args["lefts"]:
      user = self._whoami(name)
      if user is None:
        return dumps((False,))
      lefts.append(user)
    for name in args["rights"]:
      user = self._whoami(name)
      if user is None:
        return dumps((False,))
      rights.append(user)

    grid_prs = {} # {grid: [pr, ...]}
    for user in lefts+rights:
      for pr in user.personal_records:
        if pr.won is not None:
          grid = pr.general_record_id
          if grid_prs.get(grid) is None:
            grid_prs[grid] = [pr]
          else:
            grid_prs[grid].append(pr)
    games = []
    for members in grid_prs.values():
      if len(members) == len(lefts+rights):
        games.append(members)

    won_count = 0
    lost_count = 0
    for members in games:
      lefts_ = []
      rights_ = []
      for pr in members:
        if pr.user in lefts:
          lefts_.append(pr)
        if pr.user in rights:
          rights_.append(pr)
      # 左辺のUsersは味方同士ですか？
      if len(set([pr.team for pr in lefts_])) != 1:
        continue
      # 右辺のUsersは味方同士ですか？
      if rights_:
        if len(set([pr.team for pr in rights_])) != 1:
          continue
        # 左辺と右辺は敵同士でしたか？
        if lefts_[0].team == rights_[0].team:
          continue
      if lefts_[0].won:
        won_count += 1
      else:
        lost_count += 1
  # 07:13 (rakou1986) kdata rako vs kouc
  # 07:13 (galapon) 0勝0敗(-.--- 検定-.---) 参加0.00 組合0.00 連0-0 rakou1986(0.00) vs koucha(0.00)
    return dumps((True, {"won_count": won_count, "lost_count": lost_count}))

  def get_admin_list(self, json):
    args = loads(json)
    admins = db_session.query(User).filter(User.admin==True).all()
    if not admins:
      return dumps((False,))
    return dumps((True, [admin.name for admin in admins]))

  def give_authority(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    target = self._whoami(args["target"])
    if (caller is None) or (target is None):
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    target.admin = True
    db_session.commit()
    return dumps((True,))

  def deprive_authority(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    target = self._whoami(args["target"])
    if (caller is None) or (target is None):
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    target.admin = False
    db_session.commit()
    return dumps((True,))

  def update_rate(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    target = self._whoami(args["target"])
    if (caller is None) or (target is None):
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    for pr in target.personal_records:
      if pr.active:
        return dumps((False,))
    target.rate = args["rate"]
    db_session.commit()
    return dumps((True,))

  def set_user_disable(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    print [args["target"]]
    target = self._whoami(args["target"])
    if (caller is None) or (target is None):
      print 1
      print caller, target
      return dumps((False,))
    if not caller.admin:
      print 2
      print caller, target
      return dumps((False,))
    for pr in target.personal_records:
      if pr.active:
        print 3
        return dumps((False,))
    target.enable = False
    db_session.commit()
    return dumps((True,))

  def set_user_enable(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    q = db_session.query(User).filter(User.name==args["target"])
    try:
      target = q.one()
    except NoResultFound:
      target = None
    if (caller is None) or (target is None):
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    target.enable = True
    db_session.commit()
    return dumps((True,))

  def get_disable_users(self, json):
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    if caller is None:
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    users = db_session.query(User).filter(User.enable==False).all()
    if not users:
      return dumps((False,))
    return dumps((True, [user.name for user in users]))
