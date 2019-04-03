from typing import NamedTuple, List
from pprint import pprint
from requests_toolbelt.multipart.encoder import MultipartEncoder
import requests


class GlycomodComposition(NamedTuple):
    theoretical_MH: float
    delta: float
    long_notation: str
    short_notation: str
    theoretical_MTagH: float
    theoretical_MTagNa: float
    theoretical_MTagK: float
    theoretical_MTagH2: float
    theoretical_MTagHNa: float
    theoretical_MTagHK: float
    theoretical_MTagNa2: float
    theoretical_MTagNH4: float

    def __repr__(self):
        return f"Theoretical [MH]+: {self.theoretical_MH}, Delta: {self.delta}, Comp: {self.short_notation}"


class SubmittedMass(NamedTuple):
    peak_number: int
    experimental_mass: float
    adduct: str
    adduct_mass: float
    red_end_tag: str
    red_end_tag_mass: float
    glycomod_structures: List[GlycomodComposition]

    def __repr__(self):
        return f"Experimental mass: {self.experimental_mass}\n" + \
            f"Adduct: {self.adduct} ({self.adduct_mass})\n" + \
            f"Reducing end: {self.red_end_tag} ({self.red_end_tag_mass})\n" + \
            f"Compositions: {len(self.glycomod_structures)}\n"

    def prep_out(self):
        """Prepare tuples used for outputing to db and csv"""
        structure_list = []
        if len(self.glycomod_structures) > 0:
            for i in self.glycomod_structures:
                structure_list.append((
                    self.peak_number,
                    self.experimental_mass,
                    self.red_end_tag,
                    self.red_end_tag_mass,
                    # self.adduct,
                    # self.adduct_mass,
                    i.short_notation,
                    i.long_notation,
                    i.theoretical_MH,
                    i.delta,
                    i.theoretical_MTagH,
                    i.theoretical_MTagNa,
                    i.theoretical_MTagK,
                    i.theoretical_MTagNH4,
                    i.theoretical_MTagH2,
                    i.theoretical_MTagHNa,
                    i.theoretical_MTagHK,
                    i.theoretical_MTagNa2,
                ))
        return structure_list

    def prep_db_out(self):
        structure_list = []
        if len(self.glycomod_structures) > 0:
            for i in self.glycomod_structures:
                structure_list.append(
                    (self.peak_number, self.experimental_mass,
                     i.theoretical_MH, i.theoretical_MTagH, i.long_notation,
                     i.short_notation, self.red_end_tag,
                     self.red_end_tag_mass))
        return structure_list


"""THIS IS NEEDLESLY COMPLICATING THE FLOW"""


# TODO using enums for some of the fields
# TODO VALIDATION
class GMForm(NamedTuple):
    Masses: str = ""  # \n separated sequence of user masses
    masses: str = "monoisotopic"  # OPTIONS: monoisotopic, average
    upfile: tuple = ("filename", "")  # path to submitted file
    Tolerance: str = "0.5"  # mass error tolerance, unit defined in D_or_ppm
    D_or_ppm: str = "Dalton"  # mass error tolerance unit, OPTIONS: Dalton, ppm
    adducts: str = "mplus"  # ion adduct OPTIONS:
    # POSITIVE: mplus, na, k, otherplus(adduct_name1 and adduct_mass1 must be provided)
    # NEGATIVE: mminus, neutral, acetate, tfa, otherminus(adduct_name and adduct_mass must be provided)
    adduct_name1: str = ""  # for positive polarity
    adduct_mass1: str = ""  # for positive polarity
    adduct_name: str = ""  # for negative polarity
    adduct_mass: str = ""  # for negative polarity
    linked: str = "N"  # type of glycoside bond, OPTIONS: N, O
    Nform: str = "Free / PNGase released oligosaccharides"
    # glycan type of submitted mass IF linked == N
    # OPTIONS:
    # Free / PNGase released oligosaccharides
    # ENDO H or ENDO F released oligosaccharides
    # Reduced oligosaccharides
    # Derivatised oligosaccharides
    # Glycopeptides (motif N-X-S/T/C (X not P) will be used)
    Oform: str = "Glycopeptides (only those containing S or T will be used)"
    # glycan type of submitted mass IF linked == O
    # OPTIONS:
    # Free oligosaccharides
    # Reduced oligosaccharides
    # Derivatised oligosaccharides
    # Glycopeptides (only those containing S or T will be used)
    protein: str = ""  # protein sequence from which the glycan originated
    enzyme: str = "Trypsin"  # peptidase used for cleaving the protein
    # OPTIONS:
    # Trypsin (C-term to K/R, even before P)
    # Trypsin (higher specificity)
    # Trypsin/CNBr
    # Lys C
    # Lys N
    # CNBr
    # Arg C
    # Asp N
    # Asp N + N-terminal Glu
    # Asp N / Lys C
    # Asp N + N-terminal Glu / Lys C
    # Glu C (bicarbonate)
    # Glu C (phosphate)
    # Glu C (phosphate) + Lys C
    # Glu C (phosphate) + Trypsin
    # Glu C (phosphate) + Chymotrypsin
    # Chymotrypsin (C-term to F/Y/W/M/L, not before P)
    # Chymotrypsin (C-term to F/Y/W, not before P)
    # Trypsin/Chymotrypsin (C-term to K/R/F/Y/W, not before P)
    # Pepsin (pH 1.3)
    # Pepsin (pH &gt; 2)
    # Proteinase K
    # Thermolysin
    # No cutting
    MC: str = "0"  # number of cutting sites missed by the enzyme
    reagents: str = "nothing (in reduced form)"  # reagents for Cysteine treatment
    # OPTIONS:
    # nothing (in reduced form)
    # Iodoacetic acid
    # Iodoacetamide
    # 4-vinyl pyridene
    peptidemasses: str = ""  # peptide masses to provide if using Glycopeptides
    derivative_name: str = ""  # arbitrary name for a derivative IF USING Derivatized oligosaccharides
    derivative_mass: str = ""  # mass of derivative if using Derivatized oligosaccharides
    dummy: str = ""  # an empty field
    mode: str = "underivatized"  # monosaccharide residues modifications
    # OPTIONS:
    # underivatized
    # permethylated
    # peracetylated
    Hexpres: str = "yes"  # does glycan contain hexose
    Hexnb1: str = "3"  # number of hexoses LOWER limit
    Hexnb2: str = ""  # number of hexoses UPPER limit
    HexNAcpres: str = "yes"  # does glycan contain hexnac
    HexNAcnb1: str = "2"  # number of hexnac LOWER limit
    HexNAcnb2: str = ""  # number of hexnac UPPER limit
    Deoxyhexosepres: str = "possible"  # does glycan contain fucose
    Deoxyhexosenb1: str = ""  # number of fucose LOWER limit
    Deoxyhexosenb2: str = ""  # number of fucose UPPER limit
    NeuAcpres: str = "possible"  # does glycan contain neuac
    NeuAcnb1: str = ""  # number of neuac LOWER limit
    NeuAcnb2: str = ""  # number of neuac UPPER limit
    NeuGcpres: str = "no"  # does glycan contain neugc
    NeuGcnb1: str = ""  # number of neugc LOWER limit
    NeuGcnb2: str = ""  # number of neugc UPPER limit
    Pentpres: str = "no"  # does glycan contain pentoses
    Pentnb1: str = ""  # number of pentoses LOWER limit
    Pentnb2: str = ""  # number of pentoses UPPER limit
    Sulphpres: str = "possible"  # does glycan contain SO3
    Sulphnb1: str = ""  # number of SO3 LOWER limit
    Sulphnb2: str = ""  # number of SO3 UPPER limit
    Phospres: str = "possible"  # does glycan contain PO3
    Phosnb1: str = ""  # number of PO3 LOWER limit
    Phosnb2: str = ""  # number of PO3 UPPER limit
    KDNpres: str = "no"  # does glycan contain KDN
    KDNnb1: str = ""  # number of KDN LOWER limit
    KDNnb2: str = ""  # number of KDN UPPER limit
    HexApres: str = "possible"  # does glycan contain Hex-acids
    HexAnb1: str = ""  # number of Hex-acids LOWER limit
    HexAnb2: str = ""  # number of Hex-acids UPPER limit

    def to_tuples(self) -> list:
        return [(k, v) for k, v in self._asdict().items()]


if __name__ == "__main__":
    testGM = GMForm()
    encoded = MultipartEncoder(fields=(i for i in testGM.to_tuples()))
    response = requests.post(
        'http://httpbin.org/post',
        data=encoded,
        headers={'Content-Type': encoded.content_type})
    print(response.text)
