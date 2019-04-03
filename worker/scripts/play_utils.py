from utils import calc_default_adducts_mono
import json
from pprint import pprint

if __name__ == "__main__":
    with open("/home/ms/GlycomodWorkflow/GlycomodWorker/worker/config.json",
              "r") as cc:
        cfg = json.load(cc)
    comp = {"(Hex)": 3, "(HexNAc)": 2}

    results = calc_default_adducts_mono(comp, cfg, 0)
    pprint(results)