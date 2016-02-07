#!/usr/bin/env python
#coding: utf-8

"""
ゲーム募集とレーティングシステムの機能そのもの。

シングルスレッドでの利用を前提としている。
"""

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

class TamahiyoHelper(object):
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
    """
    nameからUserを探す。
    User.admin User.enable
    if True in [pr.active for pr in User.personal_records]:
    といった真偽値で、操作が可能かどうか判定するため、たいていの操作はここから始まる。

    forward_match, partial_match, backward_matchのどれかをTrueに指定する場合は、
    どれか1つだけにしなければならない。

    nameの末尾のアンダースコアは取り除かれる。
    IRCの事情をケアする仕様。
    """
    # 前方一致、部分一致、後方一致
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
      # 唯一の該当者だった場合のみ結果がほしい場合
      if one:
        if len(users) == 1:
          return users[0]
        else:
          return None
      else:
        return users if users else None
    # 完全一致
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
    """部屋番号をプールから取得"""
    rnp = self._get_rnp()
    numbers = sorted(loads(rnp.jsonstring))
    room_number = numbers.pop(0)
    rnp.jsonstring = dumps(numbers)
    db_session.flush()
    return room_number

  def _acquire_room_number(self, number):
    """部屋番号をプールに返却"""
    rnp = self._get_rnp()
    numbers = sorted(loads(rnp.jsonstring))
    numbers.append(number)
    rnp.jsonstring = dumps(numbers)
    db_session.flush()

  def _get_active_pr(self, user):
    """Userが入室中かどうか調べる。Noneなら入室中ではないということ。"""
    q = db_session.query(PersonalRecord
      ).filter(PersonalRecord.user_id == user.id
      ).filter(PersonalRecord.active == True
      )
    try:
      return q.one()
    except NoResultFound:
      return None

  def _get_dst_gr(self, channel, room_number):
    """指定された部屋番号の部屋(gr/general_record)を返す"""
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
    """参加表明"""
    pr = PersonalRecord(user.id, general_record.id)
    db_session.add(pr)
    db_session.flush()
    
  def _get_inside_member_prs(self, general_record):
    """部屋(general_record)への参加者(pr/personal_record)リスト"""
    members = []
    for pr in general_record.personal_records:
      if pr.active:
        members.append(pr)
    return members

  # 8人固定のチーム分け。任意の人数版がだめなときの予備
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

  def _team_assign(self, general_record):
    """任意の人数をチーム分け"""

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

    # チーム分け当時のレートを保存。勝敗による変動レート計算用。
    # これがないとゲーム中にレートが手動で修正されたとき、チームの合計レートが
    # 変わるせいで、勝敗によるレート変動に過不足が出る。
    for pr in team1 + team2:
      pr.rate_at_umari = pr.user.rate

    db_session.flush()

  def _is_room_owner(self, channel, caller):
    """コマンド利用者が部屋の主かどうか調べる。"""
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
    """部屋を解散する。"""
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
    """SQLAlchemyオブジェクトを、単純な辞書に構成し直す。"""
    return {
        "name": pr.user.name,
        "rate": pr.user.rate,
        "team": pr.team,
        "won": pr.won,
        "change_width": pr.change_width,
        "determined_rate": pr.determined_rate,
        }
    
  def _construct_room_info(self, gr, user=None):
    """SQLAlchemyオブジェクトを、単純な辞書に構成し直す。"""
    caller = None
    if user:
      caller = user.name
    members = []
    for pr in gr.personal_records:
      if pr.active:
        members.append(self._construct_member_info(pr))
    return {
      "id": gr.id,
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

  def _construct_result_last_60_days(self, user, won):
    """
    60日以内の勝敗情報。
    60日以上前の記録は必要ないので消す。
    表示される時には60日よりも古い記録が残っていることになるだろうが、
    表示時の現在時刻でフィルターできるので、残っていてよい。
    """
    d = loads(user.result_last_60_days)
    now = time.time()
    for key in d.keys():
      if conf._60_DAYS < now - int(key):
        d.pop(key)
    d.update({user.last_game_timestamp: won})
    return dumps(d)

  def _get_owner_pr(self, general_record):
    for pr in general_record.personal_records:
      if pr.user.name == general_record.room_owner:
        return pr
    return None
    
  def _rollback_result(self, gr):
    """勝敗の付け間違いに伴う、誤った勝敗数と、誤ったレート変動を差し戻す。"""
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
    """勝敗をつける。rollback=Trueは、訂正モード"""
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
          pr.user.last_game_timestamp = int(time.time())
    for pr in members:
      pr.won = True if pr.team == gr.winner else False
      pr.active = False
      if pr.won:
        pr.user.won_count += 1
      else:
        pr.user.lost_count += 1
      if gr.rating_match:
        cw = pr.change_width = self._calc_change_width(pr)
        pr.user.rate = pr.user.rate + (cw if pr.won else -cw)
        pr.determined_rate = pr.rate_at_umari + (cw if pr.won else -cw)
    db_session.flush()

    # 連勝記録の更新
    # 60日以内の勝敗記録
    for pr in members:
      pr.user.streak = self._get_streak(pr.user)
      pr.user.result_last_60_days = self._construct_result_last_60_days(pr.user, pr.won)
    db_session.flush()

  def _calc_change_width(self, pr):
    """
    レーティングシステムそのもの。イロレーティング。
    ただしイロレーティングでは通常K=16またはK=32とするところを、K=26としている。
    K=26は、このシステムを旧システム（イロレーティングがベース）に近づけるため、
    レート変動幅の分布を見ながら根性で探り出した経験的な値。
    """
    K = 26
    Ra, Rb = 0, 0
    for pr_ in pr.general_record.personal_records:
      if pr.team == pr_.team:
        Ra += pr_.rate_at_umari
      else:
        Rb += pr_.rate_at_umari
    Ea = 1.0 / (1 + (10**((Rb - Ra) / 400.0)))
    change_width = int(K * (int(pr.won) - Ea))
    if pr.won is False:
      change_width -= 1
    print pr.user.name, pr.won, Ra, Rb, Ea, abs(change_width)
    return abs(change_width)

  def _save_session(self, hostname, user):
    """make_room(新規ゲーム), join_room(参加表明)のとき、会員のFQDNとIPアドレスを記録する。"""
    try:
      ipaddr = unicode(socket.gethostbyname(hostname))
    except socket.gaierror: # DNSが引けないとかネット切断とか
      ipaddr = None
    db_session.add(Session(int(time.time()), hostname, ipaddr, user.id))
    db_session.flush()

  def _diff_session(self, user):
    """
    make_room(新規ゲーム), join_room(参加表明)のとき、会員のFQDNとIPアドレスが
    前回の記録から変わっているかどうか調べて、
    変わっている場合には何から何に変わったのかを返す。
    """
    diff = {}
    diff_ = False
    sessions = db_session.query(Session
      ).filter(Session.user_id == user.id
      ).order_by(Session.id.desc()
      ).limit(2
      ).all()
    if len(sessions) == 2:
      last, prev = sessions
      if (not None in [last.ipaddr, prev.ipaddr]) and (last.ipaddr != prev.ipaddr):
        diff_ = True
      if last.hostname != prev.hostname:
        diff_ = True
    if diff_:
      diff.update({
        "username": user.name,
        "last_ipaddr": last.ipaddr,
        "last_hostname": last.hostname,
        "last_timestamp": last.timestamp,
        "prev_ipaddr": prev.ipaddr,
        "prev_hostname": prev.hostname,
        "prev_timestamp": prev.timestamp,
      })
    return diff

  def _get_std_score(self, user, rates):
    """
    プレイヤーの偏差値
    偏差値(std_score)は平均(avg)と対象プレイヤーのレート(user.rate)の差を10倍して
    標準偏差(sigma_x)で割って50足したもの。
    標準偏差(sigma_x)は、「各プレイヤーの、レートと平均の差の2乗」の平均のルート。
    """
    n = len(rates)
    if n == 1:
      return 0.0
    avg = sum(rates) / float(n)
    sigma_x = math.sqrt(sum([(rate - avg)**2 for rate in rates]) / float(n))
    std_score = (((user.rate - avg) * 10) / sigma_x) + 50
    return std_score

  def _rstrip_underscore(self, s):
    """
    ルーター再起などでPing Timeoutなどを待たずにIRCに再接続すると、nicknameの
    末尾にアンダースコアが追加されることがある。

    IRCの事情に配慮して、プレイヤー名の末尾にはアンダースコアを使えない仕様にした。
    """
    return s.rstrip("_")

  def _get_streak(self, user):
    """連勝連敗数"""
    cursor = 0
    streak = 0
    while True:
      q = db_session.query(PersonalRecord
        ).filter(PersonalRecord.user_id==user.id
        ).filter(PersonalRecord.won!=None
        ).order_by(PersonalRecord.id.desc())
      try:
        pr = q.slice(cursor, cursor+1).one()
      except NoResultFound:
        break
      cursor += 1
      if streak == 0:
        streak += 1 if pr.won else -1
      elif (streak < 0) and (not pr.won):
        streak -= 1
      elif (0 < streak) and (pr.won):
        streak += 1
      else:
        break
    return streak


class TamahiyoCoreService(TamahiyoHelper):
  def __init__(self):
    super(TamahiyoCoreService, self).__init__()

  def daily_update(self):
    """
    プレイヤーのレートをプロットするFIFOキューを更新する。
    現在のレートを追加し、31個前のものは消す。
    dailyに定期実行するためのタイマーは関数を利用する側で用意する必要がある。
    """
    for user in db_session.query(User).all():
      rate_prev_30days = loads(user.rate_prev_30days)
      rate_prev_30days.append(user.rate)
      if 30 < len(rate_prev_30days):
        rate_prev_30days.pop(0)
      user.rate_prev_30days = dumps(rate_prev_30days)
    db_session.commit()

  def add_user(self, json):
    """
    たまひよ会員新規登録。
    名前の末尾のアンダースコアは取り除く。
    IRCの事情をケアする仕様。
    """
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
    db_session.commit()
    return dumps((True,))

  def delete_alias(self, json):
    """別名削除"""
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
    params = self._construct_room_info(gr, user)
    session_diff = self._diff_session(user)
    if session_diff:
      params.update({"session_diff": session_diff})
    return dumps((True, params))

  def join_room(self, json):
    """入室。参加者は8人まで。 8人になると自動でチーム分けされる。"""
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
      print [gr.umari_at, gr.rating_match]
    self._save_session(args["hostname"], user)
    db_session.commit()
    params = self._construct_room_info(gr, user)
    session_diff = self._diff_session(user)
    if session_diff:
      params.update({"session_diff": session_diff})
    return dumps((True, params))

  def umari_force(self, json):
    """参加者が8人未満のとき募集を締め切ってゲームを開始する。ノーレート戦になる"""
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

  def fix_result(self, json):
    """勝敗をつけ直す。"""
    args = loads(json)
    print args
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))

    if type(args["room_id"]) == int:
      try:
        gr = db_session.query(GeneralRecord
          ).filter(GeneralRecord.id==args["room_id"]
          ).one()
      except NoResultFound:
        return dumps((False,))
      if gr.completed_at is None:
        return dumps((False,))
      # 管理者かホスト自身だけが結果を訂正できる
      if (not user.admin) and (user.name != gr.room_owner):
        return dumps((False,))
      owner_pr = self._get_owner_pr(gr)

    else:
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
      gr = pr.general_record
      if (gr.room_owner != pr.user.name) or (gr.completed_at is None):
        return dumps((False,))
      owner_pr = pr

    self._save_result(owner_pr, args["won"], rollback=True)
    gr = owner_pr.general_record
    members = []
    for member in gr.personal_records:
      # 勝敗のついた参加者のみに限定する（入って抜けた人は除外）
      if member.won is not None:
        members.append(member)
    returns = self._construct_room_info(gr, user)
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
    """参加者"""
    args = loads(json)
    print args
    gr = self._get_dst_gr(args["channel"], args["room_number"])
    if gr is None:
      return dumps((False,))
    return dumps((True, self._construct_room_info(gr)))

  def get_hurried_members(self, json):
    """はよコマンドで呼び出されることを許可したプレイヤーリスト"""
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
    """はよコマンドで呼び出されることを許可する"""
    args = loads(json)
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    user.allow_hurry = True
    db_session.commit()
    return dumps((True,))

  def disallow_hurry(self, json):
    """はよコマンドで呼び出されることを拒否する（標準）"""
    args = loads(json)
    user = self._whoami(args["caller"])
    if user is None:
      return dumps((False,))
    user.allow_hurry = False
    db_session.commit()
    return dumps((True,))

  # 07:11 (koujan) rakou1986 719位 レート:440(先月比: 3) 戦績:136勝172敗 (勝率: 44.15%)
  def get_user_info(self, json):
    """プレイヤー情報"""
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
    """
    leftsのrightsに対する勝敗数。
    leftsとrightsには複数のプレイヤーを指定可能。
    rightsは省略可能で、その場合は単にleftsの勝敗数を返す。

    全試合を指定されたプレイヤーでAND検索し、共通の試合のうち
    敵味方関係が合うものから、勝敗数を数える。
    """
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

    # GeneralRecord.id(grid/試合)をキー、
    # GeneralRecord.personal_records(pr/参加者)を値とする辞書
    # {grid: [pr, ...]}
    grid_prs = {}
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
      # leftsのプレイヤーが味方同士でなければスキップ
      if len(set([pr.team for pr in lefts_])) != 1:
        continue
      # rightsのプレイヤーが味方同士でなければスキップ
      if rights_:
        if len(set([pr.team for pr in rights_])) != 1:
          continue
        # leftsとrightsが敵同士でなければスキップ
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
    """管理権限を付与"""
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
    """管理権限を剥奪"""
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
    """レートの手動変更"""
    args = loads(json)
    print args
    caller = self._whoami(args["caller"])
    target = self._whoami(args["target"])
    if (caller is None) or (target is None):
      return dumps((False,))
    if not caller.admin:
      return dumps((False,))
    target.rate = args["rate"]
    db_session.commit()
    return dumps((True,))

  def set_user_disable(self, json):
    """プレイヤー凍結"""
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
    """プレイヤー凍結解除"""
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
    """凍結済みプレイヤーリスト"""
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

  def get_all_players(self):
    """凍結されていない全プレイヤー。webapp用"""
    users = []
    users_ = db_session.query(User).filter(User.enable==True).order_by(User.rate.desc()).all()
    for user in users_:
      games = user.won_count + user.lost_count
      users.append({
        "rate": user.rate,
        "rate_diff_30": user.rate - loads(user.rate_prev_30days)[-1],
        "name": user.name,
        "games": games,
        "won": user.won_count,
        "lost": user.lost_count,
        "won_freq": u"%0.2f" % (user.won_count / float(games) * 100),
        "streak": user.streak,
        "last_game_timestamp": user.last_game_timestamp,
        "result_last_60_days": user.result_last_60_days,
      })
    return dumps(users)
