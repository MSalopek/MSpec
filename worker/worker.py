# -*- coding: UTF-8 -*-
import os
import logging
from collections import OrderedDict
from pprint import pprint

import arrow
import pandas as pd
from bs4 import BeautifulSoup
from toolz.itertoolz import concat
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder

from .data_types import GlycomodComposition, SubmittedMass, GMForm
from .utils import string_to_dict
from .utils import calc_default_adducts_mono
from .utils import truncated_str_from_dict


# TODO PRIMARY: MAKE USE OF CHARGES IN DB, FOR SIMPLE ADDUCTS DO TRANSFORMS TO [MH]+
# TODO TEST HOW BARE M (no adduct) is handled
# TODO this needs proper documenting
class GlycomodWorker:
    """GlycomodWorker accepts string containing N-Glycan masses
    and runs Glycomod search for all specified masses.

    ### So far only MASSES FROM POSITIVE MODE MS CAN BE USED. ###
    ### So far only H+ is USED AS ADDUCT. ###

    Results can be reported as .csv or .txt.
    Masses without matches on Glycomod are reported as NOT FOUND.

    EXAMPLE - from html - all relevant data from web
    'User mass: 1416.64',
    'Adduct ([M+H]+): 1.00727',
    'Derivative mass (Free reducing end): 18.0105546',
    '1397.5080.114(HexNAc)4 (Deoxyhexose)1 (NeuGc)1 (Pent)1',
    '1397.5080.114(Hex)1 (HexNAc)4 (NeuAc)1 (Pent)1',
    '2 structures'

    Data in EXAMPLE gets parsed and stored as objects used for reporting and calculations.

    Monoisotopic or average masses can be used.

    At this point only Da can be used when specifying mass error.
    Default mass error tolerance is 0.5 Da.

    Glycan search properties - monosaccharide presence and number(range) can be
    configured in config.json/"default_mono" and config.json/"default_occurences"
        2 -> "yes" -> monosaccharide must be present
        1 -> "possible" -> monosaccharide may be present
        0 -> "no" -> glycan MUST NOT CONTAIN specified monosaccharide
    BY DEFAULT ONLY N-glycans CONTAINING (Man)3(GlcNAc)2 ARE SELECTED
    """

    def __init__(self,
                 cfg,
                 db,
                 reducing_end=None,
                 adduct="H+",
                 adduct_extra_mass="",
                 save_txt=False,
                 filename="",
                 params=None):
        self.logger = logging.getLogger(name="Worker")
        self.cfg = cfg
        self.Nglycan_form = "Free / PNGase released oligosaccharides"
        self.adduct_info = ()
        self.adduct_extra_mass = ()
        self.adduct_form_param = ""
        self.reducing_end_tag = ""
        self.reducing_end_mass = 0.0
        self.reducing_end_mass_full = 0.0  # USED AS 'derivative_mass' field input in GM
        self.save_txt = save_txt
        self.filename = filename
        self.form_fields = None
        self.soup = None
        self.params = params
        self.parsed_data = []
        self.compositions = []
        self.masses_from_db = []
        self.masses_from_db_single = []
        self.db = db  # dbutil::DB

        self._validate_reducing_end_tag(reducing_end)
        self._validate_adduct(adduct, adduct_extra_mass)

    def _validate_reducing_end_tag(self, reducing_end):
        try:
            if reducing_end:
                self.reducing_end_tag = reducing_end
                self.reducing_end_mass = self.cfg["reducing_end_tag_mono"][
                    reducing_end]
                self.reducing_end_mass_full = self.cfg[
                    "reducing_end_tag_mono_full"][reducing_end]
                self.Nglycan_form = self.cfg["gmod_Nglycan_form"][
                    "derivatized"]
        except ValueError as e:
            self.logger.error(
                f"End tag {reducing_end} not supported, supporting only 2-AB and ProA at this point\n{e}"
            )
            raise

    def _validate_adduct(self, adduct, adduct_extra_mass):
        if adduct in self.cfg["gm_adduct_form"].keys():
            self.adduct_info = (adduct,
                                self.cfg["mono_masses_underivatized"][adduct])
            self.adduct_form_param = self.cfg["gm_adduct_form"][adduct]
            if adduct == "Pos_other" or adduct == "Neg_other":
                if adduct_extra_mass:
                    self.adduct_extra_mass = ("other", adduct_extra_mass)
                else:
                    raise ValueError(
                        "No mass value provided while using non default adduct {adduct}"
                    )
        else:
            raise ValueError(
                f"Adduct [{adduct}] not supported. Supported adducts: {list(self.cfg['gm_adduct_form'].keys())}"
            )

    def output_csv(self):
        out = list(concat([i.prep_out() for i in self.compositions]))
        df = pd.DataFrame.from_records(out, columns=self.cfg["col_names"])
        if self.filename:
            df.to_csv(str(self.filename) + ".csv", index=False)
        else:
            # set filename in case self.save_txt == True, both files should have the same name
            self.filename = f"results_{arrow.now().format('YYYYMMDD_HH:mm:ss')}"
            df.to_csv(self.filename + ".csv", index=False)
        self.logger.debug(f"Finished saving results as .csv")

    def output_text(self, to_std_out=False):
        pretty_txt = self._prettify_text()
        if to_std_out:
            print(f"SEARCH RETURNED {len(self.compositions)} RESULTS")
            print(pretty_txt)
        else:
            if self.filename:
                with open(str(self.filename) + ".txt", "w") as outfile:
                    outfile.write(pretty_txt)
            else:
                with open(
                        f"results_{arrow.now().format('YYYYMMDD_HH:mm:ss')}.txt",
                        "w") as outfile:
                    outfile.write(pretty_txt)
            self.logger.debug("Finished saving results as .txt")

    def _prettify_text(self):
        """ Transforms raw text to more readable form.
        EXAMPLE RAW:
            'User mass: 1454.0',
            'Adduct ([M+H]+): 1.00727',
            'Derivative mass (Free reducing end): 18.0105546',
            '1434.5020.48(Hex)3 (HexNAc)2 (Deoxyhexose)1 (Pent)3',
            '1435.32-0.337(Hex)1 (HexNAc)3 (Deoxyhexose)2 (Pent)1 (Sulph)3',
            '1435.362-0.379(Hex)4 (HexNAc)1 (Deoxyhexose)2 (Pent)1 (Sulph)2',
            '3 structures'
        EXAMPLE PROCESSED:
            User mass: 1454.0
            Adduct ([M+H]+): 1.00727
            Derivative mass (Free reducing end): 18.0105546
	            1. [MH]+: 1434.502,  Error: 0.48, Comp: (Hex)3(HexNAc)2(Deoxyhexose)1(Pent)3
	            2. [MH]+: 1435.32,  Error: -0.337, Comp: (Hex)1(HexNAc)3(Deoxyhexose)2(Pent)1(Sulph)3
	            3. [MH]+: 1435.362,  Error: -0.379, Comp: (Hex)4(HexNAc)1(Deoxyhexose)2(Pent)1(Sulph)2
            3 structures"""
        prep_text = self.parsed_data.copy()
        for i in prep_text:
            # if unmatched len == 4
            if len(i) > 4:
                res_string = i[3:len(i) - 1]
                prepped = []
                counter = 1
                for res in res_string:
                    split_index = res.index("(")
                    num_str, comp_str = res[:split_index:], res[split_index:]
                    comp_str = "".join(comp_str.split())
                    if num_str.find("-") > 0:  # -1 if not found
                        # [mass, error]
                        numbers = [
                            num_str[:num_str.index("-")],
                            num_str[num_str.index("-"):]
                        ]
                    else:
                        numbers = [
                            num_str[:num_str.rindex(".") - 1],
                            num_str[num_str.rindex(".") - 1:]
                        ]
                    prepped.append(
                        f"\t{counter}. [MH]+: {numbers[0]:>9},  Error: {numbers[1]:>6}, Comp: {comp_str}"
                    )
                    counter += 1
                # replace with processed strings
                i[3:len(i) - 1] = prepped
        return "\n\n".join(["\n".join(i) for i in prep_text])

    def _form_helper(self, masses_text, red_end_mass):
        if self.params:
            self.form_fields = {
                "Masses": masses_text,
                "masses": self.params["Mono/Avg"],
                "name": ("upfile", ""),
                "Tolerance": self.params["Tolerance"],
                "D_or_ppm": self.params["Unit"],
                "adducts": self.adduct_form_param,  # read from class attr
                "adduct_name1": "",  # for positive polarity
                "adduct_mass1": "",  # for positive polarity
                "adduct_name": "",  # for negative polarity
                "adduct_mass": "",  # for negative polarity
                "linked": self.params["Glycan link"],
                "Nform": self.params["N-form"],
                "Oform": "",
                "protein": "",
                "enzyme": "Trypsin",
                "MC": "0",
                "reagents": "nothing (in reduced form)",
                "peptidemasses": "",  # TODO if PEPTIDE!!!
                "derivative_name": self.params["Derivative name"],
                "derivative_mass": self.params["Derivative mass"],
                "dummy": "",
                "mode": self.params["Residue property"],
                "Hexpres": self.params["Hexpres"],
                "Hexnb1": self.params["Hexlow"],
                "Hexnb2": self.params["Hexhigh"],
                "HexNAcpres": self.params["HexNAcpres"],
                "HexNAcnb1": self.params["HexNAclow"],
                "HexNAcnb2": self.params["HexNAchigh"],
                "Deoxyhexosepres": self.params["Fucpres"],
                "Deoxyhexosenb1": self.params["Fuclow"],
                "Deoxyhexosenb2": self.params["Fuchigh"],
                "NeuAcpres": self.params["NeuAcpres"],
                "NeuAcnb1": self.params["NeuAclow"],
                "NeuAcnb2": self.params["NeuAchigh"],
                "NeuGcpres": self.params["NeuGcpres"],
                "NeuGcnb1": self.params["NeuGclow"],
                "NeuGcnb2": self.params["NeuGchigh"],
                "Pentpres": self.params["Pentpres"],
                "Pentnb1": self.params["Pentlow"],
                "Pentnb2": self.params["Penthigh"],
                "Sulphpres": self.params["SO3pres"],
                "Sulphnb1": self.params["SO3low"],
                "Sulphnb2": self.params["SO3high"],
                "Phospres": self.params["PO3pres"],
                "Phosnb1": self.params["PO3low"],
                "Phosnb2": self.params["PO3high"],
                "KDNpres": self.params["KDNpres"],
                "KDNnb1": self.params["KDNlow"],
                "KDNnb2": self.params["KDNhigh"],
                "HexApres": self.params["HexApres"],
                "HexAnb1": self.params["HexAlow"],
                "HexAnb2": self.params["HexAhigh"]
            }
        else:
            self.form_fields = {
                "Masses": masses_text,
                "masses": "monoisotopic",
                "name": ("upfile", ""),
                "Tolerance": "0.5",
                "D_or_ppm": "Dalton",
                "adducts": self.adduct_form_param,
                "adduct_name1": "",
                "adduct_mass1": "",
                "adduct_name": "",
                "adduct_mass": "",
                "linked": "N",
                "Nform": self.Nglycan_form,
                "Oform": "Glycopeptides (only those containing S or T will be used)",
                "protein": "",
                "enzyme": "Trypsin",
                "MC": "0",
                "reagents": "nothing (in reduced form)",
                "peptidemasses": "",
                "derivative_name": self.reducing_end_tag,
                "derivative_mass": red_end_mass,
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

    def _build_gm_form(self, masses_text):
        """_build_gm_form handles multipart/form preparation
        param::masses_text is a string of newline separated glycan masses
        param::custom_params is a path to json containing user specified
            analysis parameters - if not specified, somewhat restrictive
            default parameters are used:
                - mass_type: monoisotopic
                - mass_unit: Da
                - Hex count: >=3
                - HexNAc count: >=2
                - Pent: no
                - KDN: no
        """
        red_end_mass = ""
        if self.reducing_end_mass_full:
            red_end_mass = str(self.reducing_end_mass_full)
        self._form_helper(masses_text, red_end_mass)
        return MultipartEncoder(fields=(self.form_fields))

    def _calc_single_charged(self, mass, charge):
        return round(((mass * charge) - (charge - 1) * self.adduct_info[1]), 4)

    def _get_masses_from_db_single(self):
        single_ch_masses = []
        for i in self.masses_from_db:
            single_ch_masses.append((i[0], self._calc_single_charged(
                i[1], i[2])))
        return single_ch_masses

    def _load_masses_from_db(self):
        self.masses_from_db = self.db.read_current_masses()
        # transform to singly charged
        self.masses_from_db_single = self._get_masses_from_db_single()

    def _db_masses_to_text(self):
        return "\n".join([str(i[1]) for i in self.masses_from_db_single])

    def _fetch_gmod_data(self):
        masses_as_text = self._db_masses_to_text()
        gmod_form = self._build_gm_form(masses_as_text)
        head = {
            "User-Agent": self.cfg["UA"],
            'Content-Type': gmod_form.content_type
        }
        resp = requests.post(
            self.cfg["gmod_post_link"], headers=head, data=gmod_form)
        self.soup = BeautifulSoup(resp.content, 'html5lib')

    def _parse_gm_html(self) -> list:
        """Parses HTML for relevant data about glycan compositions"""
        if self.soup:
            items = []
            glycans_list = []
            for hr in self.soup.find_all("hr"):
                for item in hr.find_next_siblings():
                    if item.name == 'hr':
                        break
                    items.append(item.text)
            # this is silly
            clean_text = ''.join(items).replace(u'\nglycoform mass\nΔmass (Dalton)\nstructure\ntype\nLinks', "")\
                .replace("high_manUniCarbKB", "").replace("hybrid/complexUniCarbKB", "").\
                replace(" -UniCarbKB", "").replace("high_man", "").replace("hybrid/complex", "").\
                replace("paucimannose", "").\
                replace(" -", "").\
                replace("\n\n\n\nSIB Swiss Institute of Bioinformatics | Disclaimer", "").\
                replace("Back to the Top\n\n", "")
            unprocessed_strings = clean_text.split(
                ' found.',
                clean_text.count('found.') - 1)
            for i in unprocessed_strings:
                ll = i.split("\n")
                ll2 = []
                for j in range(len(ll)):
                    if len(ll[j]) > 1:
                        ll2.append(ll[j])
                glycans_list.append(ll2)
            self.parsed_data = glycans_list
        else:
            raise ValueError("NO GLYCOMOD DATA WAS FETCHED.")

    def _create_glycan_objects(self):
        """Creates SubmittedMass objects from parsed html data"""
        for i in range(len(self.parsed_data)):
            # masses_from_db: [(peak_number, user_mass),...]
            peak_num = self.masses_from_db[i][0]
            submitted = 0.0
            compositions = []
            for element in self.parsed_data[i]:
                if element.startswith('User mass: '):
                    submitted = element[len('User mass: '):]
                    if " " in submitted:
                        submitted = "".join(submitted.split())
                    if submitted != self.masses_from_db[i][1]:
                        self.logger.error(f"## Mismatched peak number and submitted mass\n" \
                            f"## Mass from peak data: {self.masses_from_db[i][1]}, " \
                            f"type: {type(self.masses_from_db[i][1])}\n" \
                            f"## User mass from html: {submitted}, " \
                            f"type: {type(submitted)}\n"
                            f"## peaknumber: {peak_num}\n##\n## SETTING PEAKNUM TO 0")
                        peak_num = 0
                if element[0].isdigit():
                    if "0 structures" in element:
                        compositions.append(
                            GlycomodComposition(
                                theoretical_MH=0.0,
                                delta=1000.0,
                                long_notation="NOT FOUND",
                                short_notation="NOT FOUND",
                                theoretical_MTagH=0.0,
                                theoretical_MTagNa=0.0,
                                theoretical_MTagK=0.0,
                                theoretical_MTagH2=0.0,
                                theoretical_MTagHNa=0.0,
                                theoretical_MTagHK=0.0,
                                theoretical_MTagNa2=0.0,
                                theoretical_MTagNH4=0.0,
                            ))
                    elif "structure" not in element:
                        split_index = element.index("(")
                        num_str, comp_str = element[:split_index:], element[
                            split_index:]
                        # find returns -1 if not found
                        if num_str.find("-") > 0:
                            numbers = [
                                num_str[:num_str.index("-")],
                                num_str[num_str.index("-"):]
                            ]
                        else:
                            # if positive, python handles .17 as 0.17
                            numbers = [
                                num_str[:num_str.rindex(".")],
                                num_str[num_str.rindex("."):]
                            ]
                        comp_dict = string_to_dict(comp_str)
                        # if self.use_avg_vals: # TODO
                        #    raise NotImplementedError
                        adduct_ions = calc_default_adducts_mono(
                            comp_dict,
                            self.cfg,
                            reducing_end=self.reducing_end_tag)
                        compositions.append(
                            GlycomodComposition(
                                theoretical_MH=float(numbers[0]),
                                theoretical_MTagH=adduct_ions["H+"],
                                theoretical_MTagNa=adduct_ions["Na+"],
                                theoretical_MTagK=adduct_ions["K+"],
                                theoretical_MTagH2=adduct_ions["2H2+"],
                                theoretical_MTagHNa=adduct_ions["HNa2+"],
                                theoretical_MTagHK=adduct_ions["HK2+"],
                                theoretical_MTagNa2=adduct_ions["2Na2+"],
                                theoretical_MTagNH4=adduct_ions["NH4+"],
                                delta=float(numbers[1]),
                                long_notation=comp_str,
                                short_notation=truncated_str_from_dict(
                                    comp_dict)))
            self.compositions.append(
                SubmittedMass(
                    experimental_mass=float(submitted),
                    peak_number=int(peak_num),
                    adduct=self.adduct_info[0],
                    adduct_mass=self.adduct_info[1],
                    red_end_tag=self.reducing_end_tag,
                    red_end_tag_mass=self.reducing_end_mass,
                    glycomod_structures=compositions))

    def _prepare_results(self):
        return list(concat([i.prep_db_out() for i in self.compositions]))

    def _db_masses_to_dict(self):
        masses_dict = OrderedDict()
        for i in self.masses_from_db:
            if i[0] in masses_dict.keys():
                masses_dict[i[0]].append(i[1])
            else:
                masses_dict[i[0]] = [i[1]]
        return masses_dict

    # TODO
    def _save_results(self):
        if self.compositions:
            results = self._prepare_results()
            inputted_masses_dict = self._db_masses_to_dict()
            try:
                self.db.insert_hist(inputted_masses_dict, self.form_fields, 1)
                self.db.insert_result(results)
            except Exception as e:
                print("STH WENT WRONG WHILE INSERTING", e)

    def run(self):
        """Run GlycomodWorker search and report results"""
        self._fetch_gmod_data()
        self._parse_gm_html()
        self._create_glycan_objects()
        comps_dc = [i._asdict() for i in self.compositions]
        pprint(comps_dc)
        try:
            self._save_results()
        except EnvironmentError as e:
            print("DIS VENT RONG SEVING RIZALTS", e)


if __name__ == "__main__":
    # remove "." in data_types and utils imports
    # or mess with path variables to run as script
    import json
    import dbutil
    print(
        "RUNNING WORKER AS MODULE SHOULD BE USED FOR TESTING PURPOSES ONLY!\n")
    with open(
            os.path.normpath(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "config.json")), "r") as cc:
        conf = json.load(cc)
    # CHANGE THIS TO MATCH
    #    db = dbutil.DB("/home/ms/GlycomodWorkflow/GlycomodWorker/db/testing.db")
    db = dbutil.DB("/home/ms/proj/GlycomodWorkflow/GlycomodWorker/db/testing.db")
    dbutil.setup_db_tables(db.conn)
    gw = GlycomodWorker(cfg=conf, db=db, adduct="Na+", reducing_end=None)
    gw.masses_from_db = [("1", "911.30"), ("2", "1057.33"), ("2", "913.51")] # MH+
    gw.run()
