#!/usr/bin/env python
#coding: utf-8

"""
IRCクライアント(main.py)にインタラクティブシェルとしての機能を
取り付けるためのプラグイン。

現状では #こっこ #たまひよ 専用だが、このファイルを編集すれば
どのようなシェルにも作り替えることができる。
"""

import conf

import datetime
from json import dumps, loads
import socket
import string
import xmlrpclib

import time

digits = [u"０", u"１", u"２", u"３", u"４", u"５", u"６", u"７", u"８", u"９"]
lowercases = [u"ａ", u"ｂ", u"ｃ", u"ｄ", u"ｅ", u"ｆ", u"ｇ", u"ｈ", u"ｉ", u"ｊ", u"ｋ", u"ｌ", u"ｎ", u"ｍ", u"ｏ", u"ｐ", u"ｑ", u"ｒ", u"ｓ", u"ｔ", u"ｕ", u"ｖ", u"ｗ", u"ｘ", u"ｙ", u"ｚ"]
uppercases = [u"Ａ", u"Ｂ", u"Ｃ", u"Ｄ", u"Ｅ", u"Ｆ", u"Ｇ", u"Ｈ", u"Ｉ", u"Ｊ", u"Ｋ", u"Ｌ", u"Ｎ", u"Ｍ", u"Ｏ", u"Ｐ", u"Ｑ", u"Ｒ", u"Ｓ", u"Ｔ", u"Ｕ", u"Ｖ", u"Ｗ", u"Ｘ", u"Ｙ", u"Ｚ"]
rpc = xmlrpclib.ServerProxy(conf.APISERVER)

def facade(msg):
  try:
    prefix, command, elements = parsemsg(msg.decode(conf.ENCODING))
  except UnicodeDecodeError:
    # 変な文字コードは捨てる。特にサーバーメッセージ。
    return None
  if command == "PRIVMSG":
    t_start = time.time()
    nickname, tail = prefix.split("!~")
    username, fqdn = tail.split("@")
    channel = elements[0]
    text = elements[1]
    text = text.replace(u"　", u" ")
    text = text.replace(u"＠", u"@")
    text = text.replace(u"＄", u"$")
    text = text.replace(u"／", u"/")
    text = text.replace(u"＿", u"_")
    for i, s in enumerate(digits):
      text = text.replace(s, unicode(i))
    for i, s in enumerate(lowercases):
      text = text.replace(s, unicode(string.lowercase[i]))
    for i, s in enumerate(uppercases):
      text = text.replace(s, unicode(string.uppercase[i]))
    args = {
      u"caller": nickname,
      u"channel": channel,
      u"hostname": fqdn,
      }
    try:
      if u"@" in text:
        key, argstring = text.split(u"@", 1)
        msg = commands.get(key, noop)(args, argstring)
      else:
        msg = commands.get(text, noop)(args, None)
      if (u"kokko" in text) or (u"kdata" in text):
        try:
          key, argstring = text.split(u" ", 1)
          msg = commands.get(key, noop)(args, argstring)
        except ValueError:
          msg = commands.get(text, noop)(args, None)
    except xmlrpclib.Fault, e:
      msg = mkmsg("NOTICE", args, u"「%s」の入力でエラー: %s" % (text, e.faultString))
    print time.time() - t_start
    return msg
  return None

def noop(args, argstring):
  return None

def parsemsg(msg):
  prefix = ""
  text = []
  if msg[0] == ":":
    msg = msg[1:]
  if msg.find(" ") != -1:
    prefix, msg = msg.split(" ", 1)
  if msg.find(" :") != -1:
    msg, text = msg.split(" :", 1)
    elements = msg.split()
    elements.append(text)
  else:
    elements = msg.split()
  command = elements.pop(0)
  return prefix, command, elements

def mkmsg(command, args, msg):
  return "%s %s :%s\r\n" % (command, args["channel"].encode(conf.ENCODING), msg.encode(conf.ENCODING))

def add_user(args, argstring):
  msg = u"登録できませんでした。使い方: 新規会員＠名前＠初期レート"
  if argstring:
    try:
      newcomer, rate = argstring.split(u"@", 1)
      rate = int(rate)
      if newcomer.endswith("_"):
        raise Exception
    except Exception:
      pass
    else:
      args.update({"newcomer": newcomer, "rate": rate})
      res = loads(rpc.add_user(dumps(args)))
      if res[0]:
        msg = u"%(newcomer)sさん(%(rate)d)を登録しました。" % args
  return mkmsg("NOTICE", args, msg)

def iam(args, argstring):
  msg = u"登録できませんでした。同じ名前の人がいませんか？使い方: iam＠本来の名前"
  if argstring:
    args.update({"alias": args["caller"], "original_name": argstring})
    res = loads(rpc.iam(dumps(args)))
    if res[0]:
      msg = u"%(original_name)sさんの別名「%(alias)s」を登録しました。" % args
  return mkmsg("NOTICE", args, msg)

def delete_alias(args, argstring):
  msg =u"別名を削除できませんでした。本人または管理者は、別名を削除できます。使い方: 別名削除＠別名"
  if argstring:
    args.update({"alias": argstring})
    res = loads(rpc.delete_alias(dumps(args)))
    if res[0]:
      msg = u"別名(%(alias)s)を削除しました。" % args
  return mkmsg("NOTICE", args, msg)

# 内戦？
# 00:25 (y__) [00:18:38]<purple>[1][s annpei]115.39.188.126 こっこ内戦＠１５００以下＠0 募集時間 0:03:51</purple>
# の
# 06:49 (y__) <blue>[1][r akou1986]113.37.106.25 こっこ内戦＠400以下＠6</blue> [IN]kircheis
# 埋まり
# 02:27 (y__) <blue>[1][o cham]153.218.222.138 こっこ内戦＠２０００以下＠0 募集時間 0:15:18</blue> [IN]koucha
def mk_room_str(params):
  bases = []
  s = params["room_owner"]
  params.update({"room_owner": " ".join([s[0], s[1:]])})
  if not params["game_ipaddr"]:
    params.update({"game_ipaddr": u"N/A"})
  bases.append(u"[%(room_number)d][%(id)d][%(room_owner)s]%(game_ipaddr)s こっこ内戦" % params)
  if params["room_name"]:
    bases.append(u"@%(room_name)s" % params)
  if params["umari_at"] is None:
    bases.append(u"@%d" % (8 - len(params["members"])))
  if params["umari_at"]:
    created_at = datetime.datetime.fromtimestamp(params["created_at"])
    umari_at = datetime.datetime.fromtimestamp(params["umari_at"])
    bases.append(u" 募集時間 %s" % str(umari_at - created_at))
  if params["rating_match"] is False:
    bases.append(u" [non rating]")
  return u"".join(bases)

def mk_join_str(params):
  return u" [IN]%(caller)s" % params

def mk_leave_str(params):
  return u" [OUT]%(caller)s" % params

def mk_kicked_str(params):
  return u" [OUT]%(kicked_out)s" % params

def paint_blue(s):
  return u"".join([u"\x0312", s, u"\x03"])

def paint_purple(s):
  return u"".join([u"\x036", s, u"\x03"])

def paint_green(s):
  return u"".join([u"\x033", s, u"\x03"])

def gethostbyname(hostname):
  try:
    return unicode(socket.gethostbyname(hostname))
  except socket.gaierror:
    return None

def get_team1_team2(params):
  members = sorted(params["members"], key=lambda m: (m["team"], m["rate"]))
  team1, team2 = [], []
  for member in params["members"]:
    if member["team"] == 1:
      team1.append(member)
    if member["team"] == 2:
      team2.append(member)
  team1.sort(key=lambda m: m["rate"], reverse=True)
  team2.sort(key=lambda m: m["rate"], reverse=True)
  return team1, team2

# 00:18 (y__) Team1: rabanastre kay sannpei itikan (4777)  VS  Team2: original0 HIS_0 poll ocham (4808)
def mk_team_str(params):
  team1, team2 = get_team1_team2(params)
  strings = [u"Team1: "]
  strings.append(u" ".join([member["name"] for member in team1]))
  strings.append(u" (%d)  VS  Team2: " % sum([member["rate"] for member in team1]))
  strings.append(u" ".join([member["name"] for member in team2]))
  strings.append(u" (%d)" % sum([member["rate"] for member in team2]))
  return u"".join(strings)

def mk_umari_strs(params):
  strings = []
  team1, team2 = get_team1_team2(params)
  strings.append(u" ".join([member["name"] for member in team1]))
  strings.append(u" ".join([str(member["rate"]) for member in team1]))
  strings.append(u" ".join([member["name"] for member in team2]))
  strings.append(u" ".join([str(member["rate"]) for member in team2]))
  return strings

def mk_members_str(params):
  return u", ".join([u"%(name)s(%(rate)d)" % m for m in params["members"]])
  
# 02:55 (y__) 勝利チーム : Team1
# 02:55 (y__) mutti[JP] 1676 (+13):rabanastre 1511 (+13):gdm 1334 (+13):ocham 1025 (+13):
# 02:55 (y__) koucha 1897 (-12):Hexa 1576 (-12):kircheis 1548 (-12):rakou1986 425 (-12):
def mk_result_strs(params):
  strings = []
  for member in params["members"]:
    member.update({"symbol": u"+" if member["won"] else u"-"})
    if member["change_width"] is None:
      member.update({"change_width": 0})
  team1, team2 = get_team1_team2(params)
  strings.append(u"勝利チーム : Team%(winner)d" % params)
  for team in [team1, team2]:
    strings.append(u" ".join([u"%(name)s:%(rate)d(%(symbol)s%(change_width)d)" % m for m in team]))
  return strings

def make_room(args, argstring):
  msg = u"部屋を建てられませんでした。もう入っていませんか？使い方: こっこ内戦＠説明文（＠以降は省略可）"
  args.update({"room_name": argstring})
  # APIの仕様ではrate_limitに数値を渡せば入室時にレートをチェック
  # することもできるが、現在の運用は紳士協定のようなので省略してNoneとする
  args.update({"rate_limit": None})
  args.update({"ip_addr": gethostbyname(args["hostname"])})
  res = loads(rpc.make_room(dumps(args)))
  if res[0]:
    params = res[1]
    msg = paint_blue(mk_room_str(params))
    msg = msg + mk_join_str(params)
  return "".join([mkmsg("NOTICE", args, m) for m in msg.split("\n")])

def join_room(args, argstring):
  msg = u"%(caller)sさんは部屋に入れませんでした。部屋番号は合っていますか？もう入っていませんか？使い方: の＠部屋番号" % args
  args.update({"room_number": None})
  try:
    if argstring:
      args.update({"room_number": int(argstring.strip())})
  except ValueError:
    pass
  res = loads(rpc.join_room(dumps(args)))
  if res[0]:
    params = res[1]
    msg = paint_blue(mk_room_str(params))
    msg = msg + mk_join_str(params)
    if params["umari_at"]:
      base = [mkmsg("NOTICE", args, msg)]
      base += [mkmsg("NOTICE", args, u) for u in mk_umari_strs(params)]
      base.append(mkmsg("PRIVMSG", args, mk_team_str(params)))
      return "".join(base)
  return mkmsg("NOTICE", args, msg)

def umari_force(args, argstring):
  msg = u"埋められませんでした。部屋に2人以上いて、ホストなら埋められます。"
  res = loads(rpc.umari_force(dumps(args)))
  if res[0]:
    params = res[1]
    base = [mkmsg("NOTICE", args, paint_blue(mk_room_str(params)))]
    base += [mkmsg("NOTICE", args, u) for u in mk_umari_strs(params)]
    base.append(mkmsg("PRIVMSG", args, mk_team_str(params)))
    return "".join(base)
  return mkmsg("NOTICE", args, msg)

def leave_room(args, argstring):
  msg = u"%(caller)sさんは抜けられませんでした。部屋に入っていますか？" % args
  res = loads(rpc.leave_room(dumps(args)))
  if res[0]:
    params = res[1]
    print params
    msg = paint_blue(mk_room_str(params))
    msg = msg + mk_leave_str(params)
    if params["brokeup"]:
      msgs = [
          mkmsg("PRIVMSG", args, mk_members_str(params)),
          mkmsg("NOTICE", args, paint_blue(u"%(caller)sさんは部屋を解散しました。" % args))]
      return "".join(msgs)
  return mkmsg("NOTICE", args, msg)

def kick_out(args, argstring):
  msg = u"キックできませんでした。ホストですか？名前は合っていますか？使い方: kick@名前"
  if argstring:
    args.update({"target_name": argstring})
    res = loads(rpc.kick_out(dumps(args)))
    if res[0]:
      params = res[1]
      msg = paint_blue(mk_room_str(params))
      msg = msg + mk_kicked_str(params)
  return mkmsg("NOTICE", args, msg)

def breakup(args, argstring):
  msg = u"解散できませんでした。ホストが寝てしまったら「強制解散＠部屋番号」を使ってください。"
  args.update({"force": False})
  res = loads(rpc.breakup(dumps(args)))
  if res[0]:
    params = res[1]
    msgs = [
        mkmsg("PRIVMSG", args, mk_members_str(params)),
        mkmsg("NOTICE", args, paint_blue(u"%(caller)sさんは部屋を解散しました。" % args))]
    return "".join(msgs)
  return mkmsg("NOTICE", args, msg)

def breakup_force(args, argstring):
  msg = u"解散できませんでした。番号はあっていますか？使い方: 強制解散＠部屋番号"
  if argstring:
    try:
      room_number = int(argstring)
    except ValueError:
      room_number = None
    args.update({"force": True, "room_number": room_number})
    res = loads(rpc.breakup(dumps(args)))
    if res[0]:
      params = res[1]
      msgs = [
          mkmsg("PRIVMSG", args, mk_members_str(params)),
          mkmsg("NOTICE", args, paint_blue(u"%(caller)sさんは部屋を解散しました。" % args))]
      return "".join(msgs)
  return mkmsg("NOTICE", args, msg)

def save_result_won(args, argstring):
  msg = u"勝敗をつけられませんでした。ホストですか？催促しましょう。使い方: $かち $まけ"
  args.update({"won": True})
  res = loads(rpc.save_result(dumps(args)))
  if res[0]:
    params = res[1]
    msgs = mk_result_strs(params)
    return "".join([mkmsg("NOTICE", args, m) for m in msgs])
  return mkmsg("NOTICE", args, msg)

def save_result_lost(args, argstring):
  msg = u"勝敗をつけられませんでした。ホストですか？催促しましょう。使い方: $かち $まけ"
  args.update({"won": False})
  res = loads(rpc.save_result(dumps(args)))
  if res[0]:
    params = res[1]
    msgs = mk_result_strs(params)
    return "".join([mkmsg("NOTICE", args, m) for m in msgs])
  return mkmsg("NOTICE", args, msg)

def fix_result(args, argstring):
  msg = u"ホストと管理者は、勝敗を訂正できます。ホスト視点で勝敗を入力してください。使い方: 訂正＠かち＠ゲームID 訂正＠まけ＠ゲームID"
  if argstring:
    s = argstring
    args.update({"room_id": None})

    if u"@" in s:
      won, room_id = s.strip().split(u"@", 1)
      try:
        args.update({"room_id": int(room_id.strip())})
      except Exception:
        pass
    else:
      won = s

    if won in [u"勝ち", u"かち"]:
      args.update({"won": True})
    elif won in [u"負け", u"まけ"]:
      args.update({"won": False})
    else:
      return mkmsg("NOTICE", args, msg)

    res = loads(rpc.fix_result(dumps(args)))
    if res[0]:
      params = res[1]
      msgs = mk_result_strs(params)
      return "".join([mkmsg("NOTICE", args, m) for m in msgs])
  return mkmsg("NOTICE", args, msg)

def change_game_ipaddr(args, argstring):
  msg = u"代理できませんでした。部屋に入っていますか？チャンネルは合っていますか？"
  args.update({"ip_addr": gethostbyname(args["hostname"])})
  res = loads(rpc.change_game_ipaddr(dumps(args)))
  if res[0]:
    params = res[1]
    msg = u"".join([paint_blue(mk_room_str(params)), paint_green(u"[代理]")])
  return mkmsg("NOTICE", args, msg)

def get_active_rooms(args, argstring):
  msg = u"現在、部屋はありません。"
  res = loads(rpc.get_active_rooms(dumps(args)))
  if res[1]:
    params = res[1]
    msgs = []
    for p in params:
      d = datetime.datetime.fromtimestamp(p["created_at"])
      s = u"[%s]" % d.strftime("%H:%M:%S")
      msg = paint_purple(mk_room_str(p))
      msgs.append(mkmsg("NOTICE", args, u"".join([s, msg])))
    return "".join(msgs)
  if args["caller"] == conf.NICKNAME:
    return None
  return mkmsg("NOTICE", args, msg)

def get_room_members(args, argstring):
  msg = u"参加者を取得できませんでした。部屋が複数あるときは、部屋番号を指定してください。使い方: 参加者＠部屋番号"
  try:
    args.update({"room_number": int(argstring)})
  except Exception:
    args.update({"room_number": None})
  res = loads(rpc.get_room_info(dumps(args)))
  if res[0]:
    params = res[1]
    msg = mk_members_str(params)
  return mkmsg("NOTICE", args, msg)

def call_room_members(args, argstring):
  msg = u"参加者を取得できませんでした。部屋が複数あるときは、部屋番号を指定してください。使い方: 参加者＠部屋番号"
  try:
    args.update({"room_number": int(argstring)})
  except Exception:
    args.update({"room_number": None})
  res = loads(rpc.get_room_info(dumps(args)))
  if res[0]:
    params = res[1]
    msg = mk_members_str(params)
    return mkmsg("PRIVMSG", args, msg)
  return mkmsg("NOTICE", args, msg)

def get_command_list(args, argstring):
  lines = []
  line = ""
  for command in sorted(commands.keys()):
    line = "".join([line, command, ", "])
    if 120 < len(line):
      lines.append(line)
      line = ""
  if line:
    lines.append(line)
  return "".join([mkmsg("NOTICE", args, line) for line in lines])

def get_usage_url(args, argstring):
  return mkmsg("NOTICE", args, conf.USAGE_URL)

def get_team_assign(args, argstring):
  msg = u"チーム分けを取得できませんでした。部屋が複数あるときは、部屋番号を指定してください。使い方: わけ＠部屋番号"
  try:
    args.update({"room_number": int(argstring)})
  except Exception:
    args.update({"room_number": None})
  res = loads(rpc.get_room_info(dumps(args)))
  if res[0]:
    params = res[1]
    msg = mk_team_str(params)
  return mkmsg("NOTICE", args, msg)

def get_hurried_members(args, argstring):
  msg = u"召集できる人が見つかりませんでした。"
  if argstring:
    s = argstring.replace(u"以下", u"").replace(u"いか", u"")
    try:
      args.update({"rate": int(s)})
    except Exception:
      pass
    else:
      res = loads(rpc.get_hurried_members(dumps(args)))
      if res[0]:
        names = res[1]
        if names:
          lines = []
          line = u""
          for name in names:
            line = u"".join([line, name, u"さん, "])
            if 120 < (len(line) + (line.count(u"さん") * 2)):
              lines.append(line)
              line == u""
          if line:
            lines.append(line)
          return "".join([mkmsg("PRIVMSG", args, line) for line in lines])
  return mkmsg("NOTICE", args, msg)

# args: caller, channel, hostname
def allow_hurry(args, argstring):
  msg = u"設定に失敗しました。ニックネームが変わっていませんか？"
  res = loads(rpc.allow_hurry(dumps(args)))
  if res[0]:
    msg = u"はよコマンドによる召集を許可するように設定しました。"
  return mkmsg("NOTICE", args, msg)

def disallow_hurry(args, argstring):
  msg = u"設定に失敗しました。ニックネームが変わっていませんか？"
  res = loads(rpc.disallow_hurry(dumps(args)))
  if res[0]:
    msg = u"はよコマンドによる召集を拒否するように設定しました。"
  return mkmsg("NOTICE", args, msg)

# 07:11 (koujan) rakou1986 719位 レート:440(先月比: 3) 戦績:136勝172敗 (勝率: 44.15%)
def get_user_info(args, argstring):
  msg = u"検索に失敗しました。名前はあっていますか？使用例: kokko 名前"
  if argstring:
    args.update({"username": argstring})
    res = loads(rpc.get_user_info(dumps(args)))
    if res[0]:
      lines = []
      for p in res[1]:
        p.update({"rate_diff_last_month": unicode(p["rate_current"] - p["rate_prev_30days"])})
        try:
          win_ratio = p["won_count"] / float(p["won_count"] + p["lost_count"]) * 100
        except ZeroDivisionError:
          win_ratio = 0.0
        p.update({"win_ratio": win_ratio})
        lines.append(u"%(name)s %(ranking)d位 レート:%(rate_current)d(先月比: %(rate_diff_last_month)s) 戦績: %(won_count)d勝%(lost_count)d敗 勝率%(win_ratio)0.2f%% 偏差値%(std_score)0.2f" % p)
      return "".join([mkmsg("NOTICE", args, line) for line in lines])
  return mkmsg("NOTICE", args, msg)

def get_kdata(args, argstring):
  msg = u"""検索に失敗しました。「kokko 名前」で表示される名前を指定してください。使用例: kdata 名前 / 名前（半角スラッシュ"/"で区切ると敵同士になります）"""
  s = ""
  lefts, rights = [], []
  if argstring:
    s = argstring.strip()
  if s:
    try:
      left, right = s.split(u"/")
      lefts = left.strip().split()
      rights = right.strip().split()
    except Exception:
      lefts = s.strip(u"/").strip().split()
  if lefts:
    args.update({"lefts": lefts, "rights": rights})
    print [args]
    res = loads(rpc.get_kdata(dumps(args)))
    if res[0]:
      p = res[1]
      try:
        win_ratio = p["won_count"] / float((p["won_count"] + p["lost_count"])) * 100
      except ZeroDivisionError:
        win_ratio = 0.0
      p.update({
          "win_ratio": win_ratio,
          "argstring": argstring.strip(),
          })
      msg = u"%(argstring)s: %(won_count)d勝 %(lost_count)d敗 勝率%(win_ratio)0.2f%%" % p
  return mkmsg("NOTICE", args, msg)

def get_admin_list(args, argstring):
  msg = u"管理者一覧を取得できませんでした。"
  res = loads(rpc.get_admin_list(dumps(args)))
  if res[0]:
    if res[1]:
      lines = []
      line = u""
      for name in res[1]:
        line = u"".join([line, name, u", "])
        if 120 < len(line):
          lines.append(line)
          line == u""
      if line:
        lines.append(line)
      return "".join([mkmsg("NOTICE", args, line) for line in lines])
  return mkmsg("NOTICE", args, msg)

def give_authority(args, argstring):
  msg = u"管理権限を付与できませんでした。使い方: 管理権限付与＠対象の名前"
  if argstring:
    args.update({"target": argstring.strip()})
    res = loads(rpc.give_authority(dumps(args)))
    if res[0]:
      msg = u"管理権限を付与しました。"
  return mkmsg("NOTICE", args, msg)

def deprive_authority(args, argstring):
  msg = u"管理権限を削除できませんでした。使い方: 管理権限削除＠対象の名前"
  if argstring:
    args.update({"target": argstring.strip()})
    res = loads(rpc.deprive_authority(dumps(args)))
    if res[0]:
      msg = u"管理権限を削除しました。"
  return mkmsg("NOTICE", args, msg)

def update_rate(args, argstring):
  msg = u"レートを変更できませんでした。使い方: レート変更＠対象の名前＠レート"
  if argstring:
    s = argstring
    try:
      target, rate = s.strip().split(u"@", 1)
      args.update({"target": target.strip(), "rate": int(rate.strip())})
    except Exception:
      pass
    else:
      res = loads(rpc.update_rate(dumps(args)))
      if res[0]:
        msg = u"レートを変更しました。"
  return mkmsg("NOTICE", args, msg)

def set_user_disable(args, argstring):
  msg = u"凍結できませんでした。"
  if argstring:
    args.update({"target": argstring.strip()})
    res = loads(rpc.set_user_disable(dumps(args)))
    if res[0]:
      msg = u"凍結しました。"
  return mkmsg("NOTICE", args, msg)

def set_user_enable(args, argstring):
  msg = u"凍結を解除できませんでした。"
  if argstring:
    args.update({"target": argstring.strip()})
    res = loads(rpc.set_user_enable(dumps(args)))
    if res[0]:
      msg = u"凍結を解除しました。"
  return mkmsg("NOTICE", args, msg)

def get_disable_users(args, argstring):
  msg = u"一覧を取得できませんでした。"
  res = loads(rpc.get_disable_users(dumps(args)))
  if res[0]:
    if res[1]:
      lines = []
      line = u""
      for name in res[1]:
        line = u"".join([line, name, u", "])
        if 120 < len(line):
          lines.append(line)
          line == u""
      if line:
        lines.append(line)
      return "".join([mkmsg("NOTICE", args, line) for line in lines])
  return mkmsg("NOTICE", args, msg)

commands = {
  u"新規会員": add_user,         # @
  u"iam": iam,                   # @
  u"別名削除": delete_alias,
  u"こっこ内戦": make_room,      # @
  u"の": join_room,              # @
  u"ノ": join_room,              # @
  u"no": join_room,              # @ 
  u"$うまり": umari_force,       # $
  u"$埋まり": umari_force,       # $
  u"ぬけ": leave_room,           # 
  u"抜け": leave_room,           # 
  u"nuke": leave_room,           # 
  u"kick": kick_out,             # @
  u"解散": breakup,              #
  u"強制解散": breakup_force,    # @
  u"$かち": save_result_won,     # $
  u"$勝ち": save_result_won,     # $
  u"$まけ": save_result_lost,    # $
  u"$負け": save_result_lost,    # $
  u"訂正": fix_result,      # @
  u"$代理": change_game_ipaddr,   # @
  u"$だいり": change_game_ipaddr, # @
  u"内戦？": get_active_rooms,   # 
  u"naisen?": get_active_rooms,  # 
  u"naisenn?": get_active_rooms,  # 
  u"参加者": get_room_members,   # @
  u"参加者呼び": call_room_members, # @
  u"参加者よび": call_room_members, # @
  u"はよ": get_hurried_members,
  u"はよ許可": allow_hurry,
  u"はよ不許可": disallow_hurry,
  u"わけ": get_team_assign,
  u"kokko": get_user_info,
  u"kdata": get_kdata,
  u"管理者一覧": get_admin_list,
  u"管理権限付与": give_authority,
  u"管理権限削除": deprive_authority,
  u"レート変更": update_rate,
  u"コマンド一覧": get_command_list,
  u"説明書": get_usage_url,
  u"凍結": set_user_disable,
  u"凍結解除": set_user_enable,
  u"凍結一覧": get_disable_users,
}
