import os
import logging
import unittest
import json
from bs4 import BeautifulSoup

from worker.worker import GlycomodWorker as GW
from worker.data_types import GlycomodComposition, SubmittedMass

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CFG_PATH = os.path.join(THIS_DIR, 'test_cfg.json')
logger = logging.getLogger("TEST_WORKER")

# run as
# (.venv)  GlycomodWorker (master) ✗ python -m unittest tests/test_worker.py


class TestGlycomodWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestGlycomodWorker, cls).setUpClass()
        cls.cfg = prepare_cfg()
        cls.mock_db_injection = inject_mock_db()

    def test_parsing_small(self):
        worker = GW(
            cfg=TestGlycomodWorker.cfg,
            db=TestGlycomodWorker.mock_db_injection)
        # mocking html
        worker.soup = prepare_mock_html('minimal_test.html')
        worker._parse_gm_html()
        self.assertEqual(
            worker.parsed_data,
            [[
                'User mass: 911.30', 'Adduct ([M+H]+): 1.00727',
                'Derivative mass (Free reducing end): 18.0105546',
                '892.317-0.034(Hex)3 (HexNAc)2  ', '1 structure'
            ],
             [
                 'User mass: 1057.33', 'Adduct ([M+H]+): 1.00727',
                 'Derivative mass (Free reducing end): 18.0105546',
                 '1038.375-0.062(Hex)3 (HexNAc)2 (Deoxyhexose)1  ',
                 '1 structure found.'
             ]])

    def test_create_glycan_objects(self):
        worker = GW(
            cfg=TestGlycomodWorker.cfg,
            db=TestGlycomodWorker.mock_db_injection)
        worker.parsed_data = prepare_mock_parsed_data()
        # mocking masses from db
        worker.masses_from_db = [("1", "911.30"), ("2", "1057.33")]
        worker._create_glycan_objects()
        self.assertIsInstance(worker.compositions[0], SubmittedMass)
        self.assertIsInstance(worker.compositions[0].glycomod_structures[0],
                              GlycomodComposition)
        with open("worker_test_logs.log", "w") as f:
            for i in [i._asdict() for i in worker.compositions]:
                print(i, file=f)

    def test_masses_to_text(self):
        worker = GW(
            cfg=TestGlycomodWorker.cfg,
            db=TestGlycomodWorker.mock_db_injection)
        worker.masses_from_db = [("1", "911.30"), ("2", "1057.33")]
        masses_as_text = worker._db_masses_to_text()
        self.assertEqual(masses_as_text, "911.30\n1057.33")


def prepare_mock_html(file_name):
    file_path = os.path.join(THIS_DIR, 'test_html', file_name)
    with open(file_path, "r") as f:
        html_string = f.read()
    data = BeautifulSoup(html_string, 'html5lib')
    return data


def prepare_mock_parsed_data():
    return [[
        'User mass: 911.30', 'Adduct ([M+H]+): 1.00727',
        'Derivative mass (Free reducing end): 18.0105546',
        '892.317-0.034(Hex)3 (HexNAc)2  ', '1 structure'
    ],
            [
                'User mass: 1057.33', 'Adduct ([M+H]+): 1.00727',
                'Derivative mass (Free reducing end): 18.0105546',
                '1038.375-0.062(Hex)3 (HexNAc)2 (Deoxyhexose)1  ',
                '1 structure found.'
            ]]


def prepare_cfg():
    with open(
            os.path.normpath(
                os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "test_cfg.json")), "r") as f:
        cfg = json.load(f)
    return cfg


def inject_mock_db():
    class Mockdb:
        def _get_last_result_id(self):
            pass

        def insert_hist(self, data, params, is_finished):
            pass

        @staticmethod
        def _prepare_result_entry(time, id, result):
            pass

        def insert_result(self, results):
            pass

        def insert_single_mass_into_curr(self, peak, mass):
            pass

        def read_current_masses(self):
            pass

        def clear_current_masses(self):
            pass

    return Mockdb()