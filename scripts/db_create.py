import os
import sqlite3


def setup_db_tables(db_conn):
    c = db_conn.cursor()
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("""CREATE TABLE IF NOT EXISTS history 
            (
            id INTEGER PRIMARY KEY,
            date TEXT, 
            data TEXT, 
            params TEXT, 
            finished INTEGER)""")
    c.execute("""CREATE TABLE IF NOT EXISTS results (
            date TEXT, 
            run_id INTEGER,
            peak INTEGER,
            measured REAL,
            theorMH REAL,
            theorMHTag REAL,
            comp_l TEXT,
            comp_s TEXT,
            tag TEXT,
            tag_mass REAL,
            FOREIGN KEY(run_id) REFERENCES history(id))
            """)
    c.execute("""CREATE TABLE IF NOT EXISTS curr_ephem (
        peak INTEGER,
        mass FLOAT,
        charge INTEGER)
        """)


def setup_db(path):
    conn = sqlite3.connect(path + os.sep + "store.db")
    return conn


def setup_test_db():
    conn = sqlite3.connect(
        "/home/ms/GlycomodWorkflow/GlycomodWorker/db/testing.db")
    return conn


if __name__ == "__main__":
    """ This is a script for creating the database used by the app"""
    print("SETTING UP DATABASE")
    connection = setup_test_db()
    setup_db_tables(connection)
    print("DONE SETTING UP DATABASE")