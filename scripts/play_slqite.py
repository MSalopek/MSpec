import os
import json
import datetime

import sqlite3

db = sqlite3.connect("/home/ms/GlycomodWorkflow/GlycomodWorker/db/testing.db")
c = db.cursor()

entries = c.execute("SELECT * FROM results").fetchall()

print(len(entries))
print(entries)