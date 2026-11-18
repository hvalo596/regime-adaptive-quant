"""Product universe and sector tags (DRAFT). Product codes are Tushare `fut_code`.

Sector tags are the draft groupings used for the "commodity panel first" decision
(docs/kai-dims-and-experiment-steps.md D1/D6). Availability is checked at run time: products missing from the
fetched data are simply skipped, so a wrong or stale entry here cannot create phantom data.
"""

from __future__ import annotations

EXCHANGE_SUFFIX = {"CFFEX": "CFX", "SHFE": "SHF", "DCE": "DCE", "CZCE": "ZCE", "INE": "INE", "GFEX": "GFE"}

# product -> (exchange, sector)
PRODUCTS: dict[str, tuple[str, str]] = {
    # stock index / bonds: single-product controls, not part of the commodity cross-section
    "IF": ("CFFEX", "index"), "IH": ("CFFEX", "index"), "IC": ("CFFEX", "index"), "IM": ("CFFEX", "index"),
    "TS": ("CFFEX", "bond"), "TF": ("CFFEX", "bond"), "T": ("CFFEX", "bond"), "TL": ("CFFEX", "bond"),
    # ferrous
    "RB": ("SHFE", "ferrous"), "HC": ("SHFE", "ferrous"), "SS": ("SHFE", "ferrous"),
    "I": ("DCE", "ferrous"), "J": ("DCE", "ferrous"), "JM": ("DCE", "ferrous"),
    # non-ferrous
    "CU": ("SHFE", "nonferrous"), "AL": ("SHFE", "nonferrous"), "ZN": ("SHFE", "nonferrous"),
    "PB": ("SHFE", "nonferrous"), "NI": ("SHFE", "nonferrous"), "SN": ("SHFE", "nonferrous"),
    # precious
    "AU": ("SHFE", "precious"), "AG": ("SHFE", "precious"),
    # energy / chemicals
    "SC": ("INE", "energy_chem"), "FU": ("SHFE", "energy_chem"), "BU": ("SHFE", "energy_chem"),
    "TA": ("CZCE", "energy_chem"), "MA": ("CZCE", "energy_chem"), "PP": ("DCE", "energy_chem"),
    "L": ("DCE", "energy_chem"), "V": ("DCE", "energy_chem"), "EG": ("DCE", "energy_chem"),
    "EB": ("DCE", "energy_chem"), "PG": ("DCE", "energy_chem"), "SA": ("CZCE", "energy_chem"),
    "FG": ("CZCE", "energy_chem"), "RU": ("SHFE", "energy_chem"),
    # agriculture
    "M": ("DCE", "agri"), "Y": ("DCE", "agri"), "P": ("DCE", "agri"), "A": ("DCE", "agri"),
    "C": ("DCE", "agri"), "CS": ("DCE", "agri"), "JD": ("DCE", "agri"),
    "SR": ("CZCE", "agri"), "CF": ("CZCE", "agri"), "RM": ("CZCE", "agri"), "OI": ("CZCE", "agri"),
    "AP": ("CZCE", "agri"),
}

COMMODITY_SECTORS = ("ferrous", "nonferrous", "precious", "energy_chem", "agri")


def commodity_products() -> list[str]:
    return [p for p, (_, s) in PRODUCTS.items() if s in COMMODITY_SECTORS]


def continuous_code(product: str) -> str:
    ex, _ = PRODUCTS[product]
    return f"{product}.{EXCHANGE_SUFFIX[ex]}"


# UNVERIFIED, recalled from memory and meant only for a pre/post sub-sample split, never as an exclusion rule.
# Tushare daily bars assign the night session to the NEXT trade date (exchange convention), so close-to-close
# returns stay well-defined, but products with a night session have a 24h-ish "day" whose first print is
# the night open. Replace with dates from exchange notices before drawing any conclusion from the split.
NIGHT_SESSION_START_DRAFT: dict[str, str] = {
    "AU": "2013-07-05", "AG": "2013-07-05",
    **{p: "2015-01-01" for p in (
        "CU", "AL", "ZN", "PB", "NI", "SN", "RB", "HC", "BU", "RU", "FU", "SS",
        "M", "Y", "P", "A", "J", "JM", "I", "C", "CS", "L", "V", "PP", "EG", "EB", "PG",
        "SR", "CF", "TA", "MA", "RM", "OI", "FG", "SA", "AP",
    )},
    "SC": "2018-03-26",
}

# Stock-index futures participant restrictions (draft dates, UNVERIFIED): margin/position-limit tightening after
# the 2015 crash and the later loosening steps. Used to split IF/IH/IC samples.
INDEX_RESTRICTION_DRAFT = {
    "restricted_from": "2015-09-07",
    "loosened_1": "2017-02-17",
    "loosened_2": "2019-04-22",
}
