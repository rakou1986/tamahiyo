===========================
tamahiyo ver2.0 2015/09/13
===========================

これはAge of Empires II the Conquerorsのコミュニティ「たまひよ」「こっこ」のレーティング、および対戦者マッチングシステムです。


システムの構成
=================

3つのサブシステムdbapi, ircclient, webappで構成されます。


dbapi
-----

レーティングとマッチングの、すべての機能をもっています。


ircclient
---------

コミュニティのIRCチャンネル「#たまひよ」「#こっこ」に常駐するBOTで、参加者がdbapiを利用するためのユーザーインターフェースです。


webapp
------

ircclientと同じく、dbapiのユーザーインターフェースです。


動作環境（開発環境）
========================

Ubuntu Server 12.04 LTS
Python 2.7.3
Apache 2.2.22(Ubuntu)


インストール方法
===================

次のように依存パッケージをインストールする。

pip install -r requirements.txt
aptitude install python-matplotlib=1.3.1-1ubuntu5

#TODO



使用方法
===========
#TODO


作者と連絡先
===============
たまひよ: rakou1986
rakou1986@gmail.com


ライセンス
=============


ドキュメントへのリンク
=========================


