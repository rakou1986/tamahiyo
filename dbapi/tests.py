#!/usr/bin/env python
#coding: utf-8

"""
model層のテスト。
バリデーションはAPI利用側がする。
テストはテストケースが定義されたメソッドの名前順に実行される。
メソッド名には接頭辞 test_ が必要。
"""

import conf

from json import loads, dumps
import unittest
from sqlalchemy.orm.exc import NoResultFound

from api import TamahiyoCoreAPI
from models import db_session, GeneralRecord, User, UserAlias, PersonalRecord

tama = TamahiyoCoreAPI()

def get_user(name):
  return db_session.query(User).filter(User.name==name).one()

def get_active_pr(user):
  q = db_session.query(PersonalRecord
    ).filter(PersonalRecord.active==True
    ).filter(PersonalRecord.user_id==user.id)
  try:
    return q.one()
  except NoResultFound:
    return None

user = get_user(u"rakou1986")
user.admin = True
db_session.commit()

class TamahiyoCoreTest(unittest.TestCase):
  def setUp(self):
    pass

  def test_001a_add_user(self):
    data = dumps({"newcomer": u"rakou_test_1234", "rate": 300, "caller": u"rakou1986"})
    result = loads(tama.add_user(data))
    self.assertIs(result[0], True)
    user = get_user(u"rakou_test_1234")
    self.assertEqual(user.rate, 300)

  def test_001a_add_user_reject_not_admin(self):
    data = dumps({"newcomer": u"new_sakura_1234", "rate": 300, "caller": u"sakura"})
    result = loads(tama.add_user(data))
    self.assertIs(result[0], False)
    user = get_user(u"rakou_test_1234")
    self.assertEqual(user.rate, 300)

  def test_002_add_user_reject_duplicate(self):
    data = dumps({"newcomer": u"rakou_test_1234", "rate": 300, "caller": u"rakou1986"})
    result = loads(tama.add_user(data))
    self.assertIs(result[0], False)

  def test_003_iam(self):
    data = dumps({
      "original_name": u"rakou1986",
      "alias": u"rakouの別名",
      "hostname": u"localhost",
      })
    result = loads(tama.iam(data))
    self.assertIs(result[0], True)
    user = get_user(u"rakou1986")

    self.assertIn(u"rakouの別名", [ua.name for ua in user.user_aliases])
    self.assertEqual(u"127.0.0.1", user.sessions[-1].ipaddr)

  def test_004_iam_reject_duplicate(self):
    data = dumps({
      "original_name": u"rakou1986",
      "alias": u"rakouの別名",
      "hostname": u"localhost",
      })
    result = loads(tama.iam(data))
    self.assertIs(result[0], False)

  def test_005_iam_reject_fake_user(self):
    data = dumps({
      "original_name": u"fake_user_xxx1",
      "alias": u"rakouの別名",
      "hostname": u"localhost",
      })
    result = loads(tama.iam(data))
    self.assertIs(result[0], False)

  def test_006a_make_room_reject_fake_user(self):
    data = dumps({
      "caller": u"fake_user_xxx321",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      })
    result = loads(tama.make_room(data))
    self.assertIs(result[0], False)

  def test_006b_make_room(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      })
    result = loads(tama.make_room(data))
    self.assertIs(result[0], True)
    self.assertIsInstance(result[1], dict)
    self.assertIsInstance(result[1]["created_at"], int)
    self.assertEqual(u"GA", result[1]["room_name"])
    self.assertEqual(1, result[1]["room_number"])
    gr = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.room_number==1).one()
    self.assertEqual(gr.room_owner, u"rakou1986")
    self.assertEqual(gr.channel, u"#たまひよ")
    user = get_user(u"rakou1986")
    self.assertEqual(u"127.0.0.1", user.sessions[-1].ipaddr)
    pr = get_active_pr(user)
    self.assertEqual(pr.general_record.room_owner, u"rakou1986")

  def test_007a_breakup_reject_another_channel(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#こっこ",
      "force": False,
      })
    result = loads(tama.breakup(data))
    self.assertIs(result[0], False)

  def test_007b_breakup(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "force": False,
      })
    result = loads(tama.breakup(data))
    self.assertIs(result[0], True)
    self.assertEqual(result[1]["members"][0]["name"], u"rakou1986")
    q = db_session.query(GeneralRecord).filter(GeneralRecord.active==True)
    with self.assertRaises(NoResultFound):
      q.one()

  def test_008_room_number(self):
    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      "force": False,
      }
    result = loads(tama.make_room(dumps(data)))
    self.assertEqual(1, result[1]["room_number"])

    data.update({"caller": u"koucha"})
    result = loads(tama.make_room(dumps(data)))
    self.assertEqual(2, result[1]["room_number"])

    data.update({"caller": u"aikuchi"})
    result = loads(tama.make_room(dumps(data)))
    self.assertEqual(3, result[1]["room_number"])

    data.update({"caller": u"rakou1986"})
    result = loads(tama.breakup(dumps(data)))

    data.update({"caller": u"koucha"})
    result = loads(tama.breakup(dumps(data)))

    data.update({"caller": u"galapon"})
    result = loads(tama.make_room(dumps(data)))
    self.assertEqual(1, result[1]["room_number"])

    data.update({"caller": u"ninneko"})
    result = loads(tama.make_room(dumps(data)))
    self.assertEqual(2, result[1]["room_number"])

  def test_009_make_room_numbert_user(self):
    data = dumps({
      "caller": u"fake_user_xxx2",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      })
    result = loads(tama.make_room(data))
    self.assertIs(result[0], False)

  def test_010a_join_room_reject_another_channel(self):
    data = dumps({
      "caller": u"koucha",
      "channel": u"#こっこ",
      "room_number": 1,
      "hostname": u"localhost",
      })
    result = loads(tama.join_room(data))
    self.assertIs(result[0], False)

  def test_010b_join_room(self):
    data = dumps({
      "caller": u"koucha",
      "channel": u"#たまひよ",
      "room_number": 1,
      "hostname": u"localhost",
      })
    result = loads(tama.join_room(data))
    self.assertIs(result[0], True)
    user = get_user(u"koucha")
    pr = get_active_pr(user)
    self.assertEqual(pr.general_record.room_owner, u"galapon")
    values = result[1]
    self.assertEqual(len(values["members"]), 2)
    self.assertEqual(values["room_owner"], u"galapon")

  def test_010c_join_room_another_number_and_leave(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": 2,
      "hostname": u"localhost",
      })
    result = loads(tama.join_room(data))
    self.assertIs(result[0], True)
    user = get_user(u"rakou1986")
    pr = get_active_pr(user)
    self.assertEqual(pr.general_record.room_owner, u"ninneko")
    values = result[1]
    self.assertEqual(len(values["members"]), 2)
    self.assertEqual(values["room_owner"], u"ninneko")
    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      }
    result = loads(tama.leave_room(dumps(data)))
    self.assertIs(result[0], True)

  # 1: galapon, koucha
  # 2: ninneko
  # 3: aikuchi
  def test_011_make_room_active_member(self):
    data = dumps({
      "caller": u"koucha",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      })
    result = loads(tama.make_room(data))
    gr = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.room_owner==u"koucha"
      ).all()
    self.assertIs(result[0], False)

  def test_012_make_room_update(self):
    data = dumps({
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "room_name": u"爆ラン",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      })
    result = loads(tama.make_room(data))
    self.assertIs(result[0], True)
    user = get_user(u"galapon")
    pr = get_active_pr(user)
    self.assertEqual(pr.general_record.room_name, u"爆ラン")

  # 1: galapon, koucha
  # 2: ninneko
  # 3: aikuchi
  def test_013_breakup_force_not_user(self):
    data = dumps({
      "caller": u"fake_user_xxx3",
      "channel": u"#たまひよ",
      "force": False,
      })
    result = loads(tama.breakup(data))
    self.assertIs(result[0], False)

  def test_014_force_breakup_by_inside_member_with_return_values(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": 3,
      "hostname": u"localhost",
      "force": True,
      })
    result = loads(tama.join_room(data))
    self.assertIs(result[0], True)

    result = loads(tama.breakup(data))
    self.assertIs(result[0], True)
    values = result[1]
    self.assertEqual(len(values["members"]), 2)
    for member in values["members"]:
      self.assertIn(member["name"], [u"aikuchi", u"rakou1986"])
    self.assertEqual(values["room_number"], 3)

  def test_015_force_breakup_by_outside_member_with_return_values(self):
    data = dumps({
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": 2,
      "force": True,
      })
    result = loads(tama.breakup(data))
    self.assertIs(result[0], True)
    values = result[1]
    self.assertEqual(len(values["members"]), 1)
    self.assertIn(values["members"][0]["name"], u"ninneko")
    self.assertEqual(values["room_number"], 2)

  # 1: galapon, koucha
  def test_016_join_room_umari(self):
    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": 1,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)
    
    data.update({"caller": u"aikuchi"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"ninneko"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"Hexa"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"rabanastre"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"madou"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    val = result[1]
    self.assertIsInstance(val["umari_at"], int)
    members = sorted(val["members"], key=lambda member: member["team"])
    self.assertEqual(members[0]["team"], 1)
    self.assertEqual(members[-1]["team"], 2)
    self.assertEqual(val["game_ipaddr"], u"127.0.0.1")

  # 1: galapon, koucha, rakou1986, aikuchi, ninneko, Hexa, rabanastre, madou
  def test_017_change_game_addr_reject_outsider(self):
    data = {
      "caller": u"ocham",
      "channel": u"#たまひよ",
      "ip_addr": u"192.168.1.1",
      }
    result = loads(tama.change_game_ipaddr(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(u"galapon")
    pr = get_active_pr(user)
    self.assertNotEqual(pr.general_record.game_ipaddr, u"192.168.1.1")

  def test_018_change_game_addr_reject_another_channel(self):
    data = {
      "caller": u"Hexa",
      "channel": u"#こっこ",
      "ip_addr": u"192.168.1.1",
      }
    result = loads(tama.change_game_ipaddr(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(u"galapon")
    pr = get_active_pr(user)
    self.assertNotEqual(pr.general_record.game_ipaddr, u"192.168.1.1")

  def test_019_change_game_addr(self):
    data = {
      "caller": u"Hexa",
      "channel": u"#たまひよ",
      "ip_addr": u"192.168.1.1",
      }
    result = loads(tama.change_game_ipaddr(dumps(data)))
    self.assertIs(result[0], True)
    user = get_user(u"galapon")
    pr = get_active_pr(user)
    self.assertEqual(pr.general_record.game_ipaddr, u"192.168.1.1")

  # 1: galapon, koucha, rakou1986, aikuchi, ninneko, Hexa, rabanastre, madou
  def test_020_leave_room_reject_outsider(self):
    data = {
      "caller": u"ocham",
      "channel": u"#たまひよ",
      }
    result = loads(tama.leave_room(dumps(data)))
    self.assertIs(result[0], False)

  def test_021_leave_room_reject_another_channel(self):
    data = {
      "caller": u"Hexa",
      "channel": u"#こっこ",
      }
    result = loads(tama.leave_room(dumps(data)))
    self.assertIs(result[0], False)

  def test_022_leave_room(self):
    data = {
      "caller": u"Hexa",
      "channel": u"#たまひよ",
      }
    result = loads(tama.leave_room(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    names = [member["name"] for member in val["members"]]
    self.assertNotIn(u"Hexa", names)

  # 1: galapon, koucha, rakou1986, aikuchi, ninneko, rabanastre, madou
  def test_023_kick_out_fake_user(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "target_name": u"fakeuser_xxx4567",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(data["caller"])
    pr = get_active_pr(user)
    gr = pr.general_record
    members = []
    for pr in gr.personal_records:
      if pr.active:
        members.append(pr)
    self.assertEqual(len(members), 7)

  def test_024a_kick_out_reject_outsider(self):
    data = {
      "caller": u"ocham",
      "channel": u"#たまひよ",
      "target_name": u"rakou1986",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(data["target_name"])
    pr = get_active_pr(user)
    self.assertIs(pr.active, True)

  def test_024b_kick_out_outside_member(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "target_name": u"Hexa",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], False)

  # 1: galapon, koucha, rakou1986, aikuchi, ninneko, rabanastre, madou
  def test_025_kick_out_reject_another_channel(self):
    data = {
      "caller": u"galapon",
      "channel": u"#こっこ",
      "target_name": u"koucha",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(u"koucha")
    pr = get_active_pr(user)
    self.assertIs(pr.active, True)
    
  def test_026_kick_out_reject_member(self):
    data = {
      "caller": u"rabanastre",
      "channel": u"#こっこ",
      "target_name": u"koucha",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], False)
    user = get_user(u"koucha")
    pr = get_active_pr(user)
    self.assertIs(pr.active, True)

  def test_027_kick_out(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "target_name": u"koucha",
      }
    result = loads(tama.kick_out(dumps(data)))
    self.assertIs(result[0], True)
    user = get_user(u"koucha")
    pr = get_active_pr(user)
    self.assertIs(pr, None)

  # 1: galapon, rakou1986, aikuchi, ninneko, rabanastre, madou
  def test_028_leave_room_owner(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      }
    result = loads(tama.leave_room(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    names = [member["name"] for member in val["members"]]
    self.assertIn(u"galapon", names)
    self.assertIn(u"rakou1986", names)
    self.assertIn(u"aikuchi", names)
    self.assertIn(u"ninneko", names)
    self.assertIn(u"rabanastre", names)
    self.assertIn(u"madou", names)

  def test_029a_prepare_data(self):
    data = {
      "caller": u"koucha",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      }
    result = loads(tama.make_room(dumps(data)))
    data.update({"caller": u"aikuchi"})
    result = loads(tama.make_room(dumps(data)))

  # 1: koucha
  # 2: aikuchi
  def test_029b_get_active_room(self):
    data = {"channel": u"#たまひよ"}
    result = loads(tama.get_active_rooms(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertEqual(len(val), 2)
    names = [gr["room_owner"] for gr in val]
    self.assertIn(u"koucha", names)
    self.assertIn(u"aikuchi", names)

  def test_030_join_room_omit_room_number_when_multiple_room(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], False)

  def test_031_prepare_data(self):
    data = dumps({
      "caller": u"koucha",
      "channel": u"#たまひよ",
      "force": False,
      })
    result = loads(tama.breakup(data))
    self.assertIs(result[0], True)

  # 2: aikuchi, galapon
  def test_032_join_room_omit_room_number_when_single_room(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

  def test_033_prepare_data(self):
    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"koucha"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"ninneko"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"rabanastre"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"madou"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"Hexa"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

  # 2: aikuchi, galapon, rakou1986, koucha, ninneko, rabanastre, madou, Hexa
  def test_034_join_room_9th_norio(self):
    data = {
      "caller": u"ocham",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], False)

  def test_035_save_result_reject_member(self):
    data = {
      "caller": u"ninneko",
      "channel": u"#たまひよ",
      "won": True,
      }
    result = loads(tama.save_result(dumps(data)))
    self.assertIs(result[0], False)

  def test_036_save_result_reject_outsider(self):
    data = {
      "caller": u"ocham",
      "channel": u"#たまひよ",
      "won": True,
      }
    result = loads(tama.save_result(dumps(data)))
    self.assertIs(result[0], False)

  def test_037_save_result_reject_another_channel(self):
    data = {
      "caller": u"aikuchi",
      "channel": u"#こっこ",
      "won": True,
      }
    result = loads(tama.save_result(dumps(data)))
    self.assertIs(result[0], False)

  def test_038_save_result_won_and_fix_to_lost(self):
    data = {
      "caller": u"aikuchi",
      "channel": u"#たまひよ",
      "won": True,
      }
    user = get_user(u"aikuchi")
    pr = get_active_pr(user)
    owner_team = pr.team
    gr = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.room_owner==u"aikuchi").one()
    prev_rates = {}
    [prev_rates.update({pr.user.name: pr.user.rate}) for pr in gr.personal_records]

    result = loads(tama.save_result(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertIsNot(val["umari_at"], None)
    self.assertEqual(val["winner"], owner_team)
    self.assertIn(val["winner"], [1,2])

    winners, losers = [], []
    for member in val["members"]:
      if member["team"] == owner_team:
        winners.append(member)
      else:
        losers.append(member)
    self.assertEqual(len(winners), 4)
    self.assertEqual(len(losers), 4)
    for winner in winners:
      self.assertEqual(prev_rates[winner["name"]] < winner["determined_rate"], True)
      user = get_user(winner["name"])
      self.assertEqual(winner["determined_rate"], user.rate)
    for loser in losers:
      self.assertEqual(loser["determined_rate"] < prev_rates[loser["name"]], True)
      user = get_user(loser["name"])
      self.assertEqual(loser["determined_rate"], user.rate)

    # 2: aikuchi, galapon, rakou1986, koucha, ninneko, rabanastre, madou, Hexa
    data = {"caller": u"galapon", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"koucha", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"madou", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"ocham", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"fakeuser_xxx94830", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {
      "caller": u"aikuchi",
      "won": False,
      }
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertIsNot(val["umari_at"], None)
    self.assertNotEqual(val["winner"], owner_team)
    self.assertIn(val["winner"], [1,2])

    winners, losers = [], []
    for member in val["members"]:
      if member["team"] != owner_team:
        winners.append(member)
      else:
        losers.append(member)
    self.assertEqual(len(winners), 4)
    self.assertEqual(len(losers), 4)
    for winner in winners:
      self.assertEqual(prev_rates[winner["name"]] < winner["determined_rate"], True)
      user = get_user(winner["name"])
      self.assertEqual(winner["determined_rate"], user.rate)
    for loser in losers:
      self.assertEqual(loser["determined_rate"] < prev_rates[loser["name"]], True)
      user = get_user(loser["name"])
      self.assertEqual(loser["determined_rate"], user.rate)

  def test_039_prepare_data(self):
    data = {
      "caller": u"madou",
      "channel": u"#たまひよ",
      "room_name": u"GA",
      "rate_limit": 1500,
      "hostname": u"localhost",
      "ip_addr": u"127.0.0.1",
      }
    result = loads(tama.make_room(dumps(data)))
    self.assertIs(result[0], True)

    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"koucha"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"ninneko"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

    data.update({"caller": u"rabanastre"})
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], True)

  # 1: madou, rakou1986, koucha, ninneko, rabanastre
  def test_040_umari_force_reject_member(self):
    data = {
      "caller": u"rakou1986",
      "channel": u"#たまひよ",
      }
    result = loads(tama.umari_force(dumps(data)))
    self.assertIs(result[0], False)

  def test_041_umari_force_reject_fake_user(self):
    data = {
      "caller": u"fakeuser_xxx9839420",
      "channel": u"#たまひよ",
      }
    result = loads(tama.umari_force(dumps(data)))
    self.assertIs(result[0], False)

  def test_042_umari_force_reject_outsider(self):
    data = {
      "caller": u"aikuchi",
      "channel": u"#たまひよ",
      }
    result = loads(tama.umari_force(dumps(data)))
    self.assertIs(result[0], False)

  def test_043_umari_force_reject_another_channel(self):
    data = {
      "caller": u"madou",
      "channel": u"#こっこ",
      }
    result = loads(tama.umari_force(dumps(data)))
    self.assertIs(result[0], False)

  def test_044_umari_force(self):
    data = {
      "caller": u"madou",
      "channel": u"#たまひよ",
      }
    result = loads(tama.umari_force(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertIsNot(val["umari_at"], None)

  # 1: madou, rakou1986, koucha, ninneko, rabanastre
  def test_045_norio(self):
    data = {
      "caller": u"galapon",
      "channel": u"#たまひよ",
      "room_number": None,
      "hostname": u"localhost",
      }
    result = loads(tama.join_room(dumps(data)))
    self.assertIs(result[0], False)

  # 1: madou, rakou1986, koucha, ninneko, rabanastre
  def test_046_save_result_won_and_fix_to_lost(self):
    data = {
      "caller": u"madou",
      "channel": u"#たまひよ",
      "won": False,
      }
    user = get_user(u"madou")
    pr = get_active_pr(user)
    owner_team = pr.team
    gr = db_session.query(GeneralRecord
      ).filter(GeneralRecord.active==True
      ).filter(GeneralRecord.room_owner==u"madou").one()
    prev_rates = {}
    [prev_rates.update({pr.user.name: pr.user.rate}) for pr in gr.personal_records]

    result = loads(tama.save_result(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertIsNot(val["umari_at"], None)
    self.assertNotEqual(val["winner"], owner_team)
    self.assertIn(val["winner"], [1,2])

    winners, losers = [], []
    for member in val["members"]:
      if member["team"] != owner_team:
        winners.append(member)
      else:
        losers.append(member)
    self.assertIn(len(winners), [2,3])
    self.assertIn(len(losers), [2,3])
    for winner in winners:
      self.assertEqual(prev_rates[winner["name"]] < winner["determined_rate"], True)
      user = get_user(winner["name"])
      self.assertEqual(winner["determined_rate"], user.rate)
    for loser in losers:
      self.assertEqual(loser["determined_rate"] < prev_rates[loser["name"]], True)
      user = get_user(loser["name"])
      self.assertEqual(loser["determined_rate"], user.rate)

    # 1: madou, rakou1986, koucha, ninneko, rabanastre
    data = {"caller": u"rakou1986", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"koucha", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"ninneko", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"rabanastre", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"ocham", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {"caller": u"fakeuser_xxx94830", "won": False}
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], False)

    data = {
      "caller": u"madou",
      "won": True,
      }
    result = loads(tama.fix_prev_result(dumps(data)))
    self.assertIs(result[0], True)
    val = result[1]
    self.assertIsNot(val["umari_at"], None)
    self.assertEqual(val["winner"], owner_team)
    self.assertIn(val["winner"], [1,2])

    winners, losers = [], []
    for member in val["members"]:
      if member["team"] == owner_team:
        winners.append(member)
      else:
        losers.append(member)
    self.assertIn(len(winners), [2,3])
    self.assertIn(len(losers), [2,3])
    for winner in winners:
      self.assertEqual(prev_rates[winner["name"]] < winner["determined_rate"], True)
      user = get_user(winner["name"])
      self.assertEqual(winner["determined_rate"], user.rate)
    for loser in losers:
      self.assertEqual(loser["determined_rate"] < prev_rates[loser["name"]], True)
      user = get_user(loser["name"])
      self.assertEqual(loser["determined_rate"], user.rate)

if __name__ == '__main__':
  unittest.main()
