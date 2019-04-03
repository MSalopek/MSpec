# -*- coding: UTF-8 -*-
import logging
from .gui import App
from .ms_utils import get_chromatograms
from PyQt5 import Qt, QtGui, QtCore
import argparse

# TODO: SHOW TABLE IN GUI
# TODO: Add gui sugar: UNDO, REDO, FILE(MENU), EDIT(MENU: charge, mass, reducing end),
#       TOOLS:
#           PROCESSING OPTIONS: centroid(for continuous data) deisotope, deconvolute
#           smoothing, subtract noise, filter masses - DON'T SHOW IN SPECTRUM),

parser = argparse.ArgumentParser(
    description="""N-Glycan MS Data preliminary analysis tool.
Please provide path to file to start GUI
All masses are submitted as [MH]+, calculated to be singly charged m/z to simplify Glycomod search
The program returns .csv and/or .txt file as results""")

parser.add_argument(
    "--file", '-f', help="Specify ABSOLUTE path to file", required=True)
parser.add_argument(
    "--db", '-db', help="Path to database. Test db is in ./db/testing.db - Provide a valid path to that file.")
parser.add_argument(
    "--debug", help="Print debug logs to console", action="store_true")
parser.add_argument(
    "--text",
    help="Save search results as .txt. Default: save search as .csv",
    action="store_true")

args = vars(parser.parse_args())

if __name__ == "__main__":
    from .worker import dbutil
    db = dbutil.DB(args["db"])
    path = args["file"]
    app = QtGui.QApplication([])
    if args["debug"]:
        logging.basicConfig(
            format='[%(levelname)s][%(module)s] %(message)s',
            level=logging.DEBUG)
    else:
        logging.basicConfig(
            format='[%(levelname)s][%(module)s] %(message)s',
            level=logging.ERROR)

    chrs = get_chromatograms(path)
    w = App(path, chrs, db)
    w.plotChroms(chrs)
    app.exec_()
