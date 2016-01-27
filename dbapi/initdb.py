#!/user/bin/env python
# coding: utf-8

from models import *
import migration

def initialize():
  Base.metadata.drop_all(engine)
  Base.metadata.create_all(engine)
  migration.main()

if __name__ == "__main__":
  initialize()
