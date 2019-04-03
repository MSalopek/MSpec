import worker

custom_p = {
    "masses": "monoisotopic",
    "name": ("upfile", ""),
    "Tolerance": "0.5",
    "D_or_ppm": "Dalton",
    "adducts": "na",
    "adduct_name1": "",
    "adduct_mass1": "",
    "adduct_name": "",
    "adduct_mass": "",
    "linked": "N",
    "Nform": "Free / PNGase released oligosaccharides",
    "Oform": "Glycopeptides (only those containing S or T will be used)",
    "protein": "",
    "enzyme": "Trypsin",
    "MC": "0",
    "reagents": "nothing (in reduced form)",
    "peptidemasses": "",
    "derivative_name": "",
    "derivative_mass": "",
    "dummy": "",
    "mode": "underivatised",
    "Hexpres": "yes",
    "Hexnb1": "3",
    "Hexnb2": "",
    "HexNAcpres": "yes",
    "HexNAcnb1": "2",
    "HexNAcnb2": "",
    "Deoxyhexosepres": "possible",
    "Deoxyhexosenb1": "",
    "Deoxyhexosenb2": "",
    "NeuAcpres": "possible",
    "NeuAcnb1": "",
    "NeuAcnb2": "",
    "NeuGcpres": "no",
    "NeuGcnb1": "",
    "NeuGcnb2": "",
    "Pentpres": "no",
    "Pentnb1": "",
    "Pentnb2": "",
    "Sulphpres": "possible",
    "Sulphnb1": "",
    "Sulphnb2": "",
    "Phospres": "possible",
    "Phosnb1": "",
    "Phosnb2": "",
    "KDNpres": "no",
    "KDNnb1": "",
    "KDNnb2": "",
    "HexApres": "possible",
    "HexAnb1": "",
    "HexAnb2": ""
}

if __name__ == "__main__":
    from pprint import pprint
    import json
    import dbutil
    with open("/home/ms/GlycomodWorkflow/GlycomodWorker/worker/config.json",
              "r") as cc:
        conf = json.load(cc)
    db = dbutil.DB("/home/ms/GlycomodWorkflow/GlycomodWorker/db/testing.db")
    dbutil.setup_db_tables(db.conn)
    gw = worker.GlycomodWorker(cfg=conf, db=db, reducing_end=None)
    gw.masses_from_db = [("1", "933.33")]
    gw.custom_params = custom_p
    gw.run()
    gw.output_text(to_std_out=True)
