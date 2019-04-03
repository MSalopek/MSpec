import logging
from pyteomics import mzml, mzxml
import numpy as np
from bisect import bisect_left

logger = logging.getLogger(__name__)


def get_ms1_basepeak(path: str) -> list:
    peaks = []  # [[retention time, base mz], ... ]
    if path.endswith(".mzXML") or path.endswith(".mzxml"):
        with mzxml.read(path) as data:
            for scan in data:
                if scan["ms level"] == 1:
                    arr = scan["m/z array"]
                    basepeak = round(scan["base peak m/z"], 6)
                    charge = check_charge_state_centroid(arr, basepeak)
                    if charge != 0:
                        peaks.append(
                            (scan["scanList"]["scan"][0]["scan start time"],
                             basepeak, charge))
        return peaks

    with mzml.read(path) as data:
        for scan in data:
            if scan["ms level"] == 1:
                arr = scan["m/z array"]
                basepeak = round(scan["base peak m/z"], 2)
                charge = check_charge_state_centroid(arr, basepeak)
                if charge != 0:
                    peaks.append(
                        (scan["scanList"]["scan"][0]["scan start time"],
                         basepeak, charge))
    return peaks


def get_chromatograms(path: str):
    with mzml.read(path) as reader:
        retention_times = []
        TIC = []
        BPI = []
        for scan in reader:
            if scan["ms level"] == 1 and scan["scanList"]["scan"][0][
                    "scan start time"] > 7.5:
                retention_times.append(
                    scan["scanList"]["scan"][0]["scan start time"])
                TIC.append(scan["total ion current"])
                BPI.append(scan["base peak intensity"])
        retention_times = np.array(retention_times)
        TIC = np.array(TIC)
        BPI = np.array(BPI)
        chrom_data = {
            "retention_times": retention_times,
            "TIC": TIC,
            "BPI": BPI
        }
        return chrom_data


# TODO ERROR HANDLING
def get_spectrum(retention_time, path):
    with mzml.read(path) as reader:
        for scan in reader:
            if scan["scanList"]["scan"][0][
                    "scan start time"] == retention_time:
                mz = scan["m/z array"]
                intensity = scan["intensity array"]
                scan_type = "DISCRETE"
                if "centroid spectrum" in scan.keys():
                    scan_type = "CENTROID"
                return mz, intensity, scan_type


def check_charge_state_centroid(np_array, mz) -> int:
    """Determines charged state from provided numpy array and mz value
    for centroided peak data"""
    try:
        mz_pos = np.where(np_array == mz)
        next_pos_val = np_array[mz_pos[0] + 1]
    except Exception as e:
        logger.error(
            f"Error checking charge state for continuous peaks. DETAILS:\n##########\n{e}"
        )
        return 0
    # allowing for measurement errors
    if next_pos_val - mz < 0.27:
        return 4
    elif next_pos_val - mz < 0.4:
        return 3
    elif next_pos_val - mz < 0.6:
        return 2
    elif next_pos_val - mz < 1.15:
        return 1
    else:
        logger.error(
            f"Error checking charged state for continuous peaks. Inputs: ###{np_array}\n###{mz}"
        )
        return 0


def check_charge_state_continuous(np_array, mz) -> int:
    pass


def get_closest_point(point, x_values: list):
    """
    Returns closest value to point.
    If two numbers are equally close, return the smallest number.
    Runs O(log n)
    MODIFIED FROM: Lauritz V. Thaulow answer on StackOverflow
    https://stackoverflow.com/questions/12141150/from-list-of-integers-get-number-closest-to-a-given-value/12141511#12141511
    """
    pos = bisect_left(x_values, point)
    if pos == 0:
        return x_values[0]
    if pos == len(x_values):
        return x_values[-1]
    before = x_values[pos - 1]
    after = x_values[pos]
    if after - point < point - before:
        return after
    else:
        return before


def primitive_peak_find(intensity_array):
    """Main purpose is to de-clutter the view - too many annotations in view."""
    int_list = list(intensity_array)
    max_y = max(int_list)
    indexes = []
    # numbers are arbitrary, this is just for quick prototyping
    if max_y > 400000:  
        for i, j in enumerate(int_list):
            if j > max_y*0.005:
                indexes.append(i)
        return indexes
    if 200000 < max_y < 400000: 
        for i, j in enumerate(int_list):
            if j > max_y*0.01:
                indexes.append(i)
        return indexes
    if 50000 < max_y < 200000:
        for i, j in enumerate(int_list):
            if j > max_y*0.05:
                indexes.append(i)
        return indexes
    else:
        for i, j in enumerate(int_list):
            if j > max_y*0.2:
                indexes.append(i)
        return indexes
