"""Product universe and sector tags (DRAFT). Product codes are Tushare `fut_code`.

Sector tags are the draft groupings used for the "commodity panel first" decision
(docs/kai-dims-and-experiment-steps.md D1/D6). Availability is checked at run time: products missing from the
fetched data are simply skipped, so a wrong or stale entry here cannot create phantom data.
"""

from __future__ import annotations

import pandas as pd

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


# Night (continuous-trading) sessions: EVENING of the first session, from exchange notices (checked 2026-11-21 against SHFE's
# "连续交易业务专题", DCE monthly reports 2015-05 / 2019-03 and the 2020-04-24 notice, CZCE notices 2014-12-05 and 2015-06-02).
# A night session belongs to the NEXT trade date (exchange definition: "前一工作日21:00至当天15:00"), so the first trade date whose
# bar contains a night print is the next business day (Monday for a Friday evening). The earlier draft table put 2015-01-01 on
# almost every product, which was wrong by up to 51 months (DCE L, V, PP, EG, C, CS) (copper group 2013-12-20, rebar group and DCE oilseed/metals 2014-12-26,
# CZCE first batch 2014-12-12, DCE chemicals and corn 2019-03-29).
NIGHT_SESSION_EVENING: dict[str, tuple[str, str]] = {
    "AU": ("2013-07-05", "verified"), "AG": ("2013-07-05", "verified"),
    "CU": ("2013-12-20", "verified"), "AL": ("2013-12-20", "verified"), "ZN": ("2013-12-20", "verified"), "PB": ("2013-12-20", "verified"),
    "RB": ("2014-12-26", "verified"), "HC": ("2014-12-26", "verified"), "RU": ("2014-12-26", "verified"), "BU": ("2014-12-26", "verified"),
    "NI": ("2015-03-27", "verified (listing day; evening of listing assumed)"), "SN": ("2015-03-27", "verified (listing day; evening of listing assumed)"),
    "J": ("2014-07-04", "verified"), "P": ("2014-07-04", "verified"),
    "M": ("2014-12-26", "verified"), "Y": ("2014-12-26", "verified"), "A": ("2014-12-26", "verified"), "JM": ("2014-12-26", "verified"), "I": ("2014-12-26", "verified"),
    "L": ("2019-03-29", "verified"), "V": ("2019-03-29", "verified"), "PP": ("2019-03-29", "verified"), "EG": ("2019-03-29", "verified"), "C": ("2019-03-29", "verified"), "CS": ("2019-03-29", "verified"),
    "PG": ("2020-05-06", "verified (night added at the 2020-05 resumption)"),
    "SR": ("2014-12-12", "verified"), "CF": ("2014-12-12", "verified"), "RM": ("2014-12-12", "verified"), "MA": ("2014-12-12", "verified"), "TA": ("2014-12-12", "verified"),
    "OI": ("2015-06-11", "verified"), "FG": ("2015-06-11", "verified"),
    "SC": ("2018-03-26", "verified (listing day)"),
    # not verified: SS (listed 2019-09-25), FU, EB, SA (listed 2019-12-06): night from listing assumed, FU date unknown
    "SS": ("2019-09-25", "unverified: night from listing assumed"), "SA": ("2019-12-06", "unverified: night from listing assumed"),
    "EB": ("2019-09-26", "unverified: night from listing assumed"), "FU": ("2018-07-16", "unverified: date not found"),
    # no night session: JD, AP (and all CFFEX products)
}
NIGHT_SESSION_START_DRAFT: dict[str, str] = {p: (pd.Timestamp(d) + pd.offsets.BDay(1)).strftime("%Y-%m-%d") for p, (d, _) in NIGHT_SESSION_EVENING.items()}
# Night sessions of all commodity products were suspended from the evening of 2020-02-03 and resumed on the evening of 2020-05-06.
NIGHT_SUSPENSION_TRADE_DATES = ("2020-02-04", "2020-05-06")

# Stock-index futures participant restrictions, verified 2026-11-21 against CFFEX notices (2015-09-02, 2017-02-17, 2018-12-02, 2019-04-19):
# 2015-09-07 margin 40% / intraday opening limit 10 lots / close-today fee 23 bp; 2017-02-17 first loosening; 2017-09-18 IF, IH margin 20% -> 15%;
# 2018-12-03 margin 10/10/15% and limit 50 lots; 2019-04-22 IC margin 12% and limit 500 lots. The earlier draft missed 2017-09-18 and 2018-12-03.
INDEX_RESTRICTION_DRAFT = {
    "restricted_from": "2015-09-07",
    "loosened_1": "2017-02-17",
    "loosened_2": "2017-09-18",
    "loosened_3": "2018-12-03",
    "loosened_4": "2019-04-22",
}
