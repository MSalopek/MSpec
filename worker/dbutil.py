import os
import json
import datetime

import sqlite3


def setup_db_tables(db_conn):
    c = db_conn.cursor()
    # if there's an error save to db with finished 0
    # have it in nice row or separate results out:
    #       peak:mass (variadic)
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


# TODO: output results as csv
class DB:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)

    def __del__(self):
        self.conn.close()

    def close(self):
        self.__del__()

    def _get_last_result_id(self) -> int:
        with self.conn as conn:
            # if table is empty fetchone() returns (None, )
            res_id = conn.execute("SELECT MAX(run_id) FROM results").fetchone()
        if res_id[0] is not None:
            return res_id[0]
        return 0

    def insert_hist(self, data, params, is_finished):
        # TODO LOGGING
        time = datetime.datetime.now().isoformat()
        data_json = json.dumps(data)
        params_json = json.dumps(params)
        # None needs to be passed for sqlite autoincrement to work
        values_tuple = (None, time, data_json, params_json, is_finished)
        try:
            with self.conn as conn:
                conn.execute("INSERT INTO history values (?, ?, ?, ?, ?)",
                             values_tuple)
        except Exception as e:
            print(f"FAILED INSERTING HIST WITH ERR: {e}")

    @staticmethod
    def _prepare_result_entry(time, id, result):
        return (time, id, *result)

    def insert_result(self, results):
        time = datetime.datetime.now().isoformat()
        last_res_id = self._get_last_result_id()
        current_res_id = last_res_id + 1
        prepared_results = [
            self._prepare_result_entry(time, current_res_id, i)
            for i in results
        ]
        try:
            with self.conn as conn:
                conn.executemany(
                    "INSERT INTO results values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    prepared_results)
        except Exception as e:
            print("FAILED INSERTING RESULTS", e)

    def insert_single_mass_into_curr(self, peak, mass):
        try:
            with self.conn as conn:
                c = conn.cursor()
                c.execute("INSERT INTO curr_ephem values (?, ?)", peak, mass)
        except Exception as err:
            print("Error inserting single mass into db:", err)

    def insert_many_masses_into_curr(self, peaks_data):
        """param:peaks_data [(peak, mass, charge)...]"""
        try:
            with self.conn as conn:
                c = conn.cursor()
                c.executemany("INSERT INTO curr_ephem values (?, ?, ?)",
                              peaks_data)
        except Exception as err:
            print("Error inserting multiple masses into db:", err)

    def read_current_masses(self):
        current_masses = []
        try:
            with self.conn as conn:
                # returns rows as list of tuples
                current_masses = conn.execute(
                    "SELECT * FROM curr_ephem").fetchall()
        except Exception as err:
            print("DB ERR FAILED READING CURR_EPHEM", err)
            return current_masses
        return current_masses

    def clear_current_masses(self):
        try:
            with self.conn as conn:
                conn.execute("DELETE FROM curr_ephem")
        except Exception as e:
            print("FAILED CLEANING CURRENT MASSES", e)

    def read_result(self):
        # read in results:
        # all, clicked run, select multiple runs
        pass

    def read_history(self):
        pass
        # read in all history - make clickable

    def output_csv(self, table, id=None, start=None, end=None):
        # output to csv from table, id=col_name, start, end = row_id start, row_id end
        pass

    def output_text(self, table, id=None, start=None, end=None):
        pass
