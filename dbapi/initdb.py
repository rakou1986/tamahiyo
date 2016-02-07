#!/user/bin/env python
# coding: utf-8

from models import *

def initialize():
  Base.metadata.drop_all(engine)
  Base.metadata.create_all(engine)
  import migration
  migration.main()

if __name__ == "__main__":
  initialize()
