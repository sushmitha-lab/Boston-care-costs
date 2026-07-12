"""Parsers for CMS Hospital Price Transparency MRFs (schema v2.x / v3.x).

Both parsers emit the same flat record dict per (item, setting, payer) row:

    hospital_id, hospital_name, last_updated_on, mrf_version,
    description, setting,
    code_1, code_1_type, code_2, code_2_type,
    gross_charge, discounted_cash,
    payer_name, plan_name, negotiated_dollar, negotiated_percentage,
    negotiated_algorithm, methodology, min_charge, max_charge

Real-world files violate the spec constantly (prices as "$1,234.00",
"N/A" filler, blank strings, ranges). `_money()` is deliberately
forgiving and returns None on anything non-numeric; the data-quality
layer downstream counts what was dropped.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from pathlib import Path
from typing import Iterator

log = logging.getLogger("hpt.parsers")

_MONEY_JUNK = re.compile(r"[$,\s]")
_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")


def _money(value) -> float | None:
    """Coerce a price cell to float; None for filler/garbage.

    Handles: 1234.5, "1234.50", "$1,234.50", "  999 ", "", "N/A",
    "Null", "None", "-", "9999999999" sentinel (nine 9s per CMS FAQ).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
    else:
        s = _MONEY_JUNK.sub("", str(value)).strip()
        if not s or not _NUMERIC.match(s):
            return None
        v = float(s)
    if v < 0 or v == 999999999:  # CMS sentinel for "not calculable"
        return None
    return v


def _clean(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s and s.lower() not in {"n/a", "na", "null", "none", "-"} else None


# --------------------------------------------------------------------------
# Tall CSV
# --------------------------------------------------------------------------

def parse_tall_csv(path: Path, hospital_id: str) -> Iterator[dict]:
    """Parse a CMS tall-format CSV.

    Layout: row 1 = metadata labels, row 2 = metadata values,
    row 3 = column headers, rows 4+ = data. Column headers use the
    pipe convention, e.g. `standard_charge | negotiated_dollar`.
    """
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))

    meta_labels = next(reader)
    meta_values = next(reader)
    meta = {
        _norm_header(k): _clean(v)
        for k, v in zip(meta_labels, meta_values)
        if _clean(k)
    }
    hospital_name = meta.get("hospital_name")
    last_updated = meta.get("last_updated_on")
    version = meta.get("version")

    headers = [_norm_header(h) for h in next(reader)]
    idx = {h: i for i, h in enumerate(headers)}

    def cell(row: list[str], key: str) -> str | None:
        i = idx.get(key)
        return row[i] if i is not None and i < len(row) else None

    n_rows = 0
    for row in reader:
        if not any(c.strip() for c in row):
            continue
        n_rows += 1
        yield {
            "hospital_id": hospital_id,
            "hospital_name": hospital_name,
            "last_updated_on": last_updated,
            "mrf_version": version,
            "description": _clean(cell(row, "description")),
            "setting": _clean(cell(row, "setting")),
            "code_1": _clean(cell(row, "code|1")),
            "code_1_type": _clean(cell(row, "code|1|type")),
            "code_2": _clean(cell(row, "code|2")),
            "code_2_type": _clean(cell(row, "code|2|type")),
            "gross_charge": _money(cell(row, "standard_charge|gross")),
            "discounted_cash": _money(cell(row, "standard_charge|discounted_cash")),
            "payer_name": _clean(cell(row, "payer_name")),
            "plan_name": _clean(cell(row, "plan_name")),
            "negotiated_dollar": _money(cell(row, "standard_charge|negotiated_dollar")),
            "negotiated_percentage": _money(cell(row, "standard_charge|negotiated_percentage")),
            "negotiated_algorithm": _clean(cell(row, "standard_charge|negotiated_algorithm")),
            "methodology": _clean(cell(row, "standard_charge|methodology")),
            "min_charge": _money(cell(row, "standard_charge|min")),
            "max_charge": _money(cell(row, "standard_charge|max")),
        }
    log.info("%s: parsed %d tall-CSV rows", hospital_id, n_rows)


def _norm_header(h: str) -> str:
    """`standard_charge | Negotiated_Dollar ` -> `standard_charge|negotiated_dollar`"""
    return "|".join(p.strip().lower() for p in str(h).split("|")).strip()


# --------------------------------------------------------------------------
# JSON
# --------------------------------------------------------------------------

def parse_json_mrf(path: Path, hospital_id: str) -> Iterator[dict]:
    """Parse a CMS JSON-format MRF (v2.x/v3.x `standard_charge_information`)."""
    with path.open("rb") as f:
        doc = json.load(f)

    hospital_name = _clean(doc.get("hospital_name"))
    last_updated = _clean(doc.get("last_updated_on"))
    version = _clean(doc.get("version"))

    items = doc.get("standard_charge_information") or []
    n_rows = 0
    for item in items:
        desc = _clean(item.get("description"))
        codes = item.get("code_information") or []
        _prio = {"CPT": 0, "HCPCS": 1, "MS-DRG": 2, "DRG": 3, "APR-DRG": 4}
        ranked = sorted(
            codes,
            key=lambda c: _prio.get(str(c.get("type", "")).upper().strip(), 99),
        )
        code_1 = _clean(ranked[0].get("code")) if len(ranked) > 0 else None
        code_1_type = _clean(ranked[0].get("type")) if len(ranked) > 0 else None
        code_2 = _clean(ranked[1].get("code")) if len(ranked) > 1 else None
        code_2_type = _clean(ranked[1].get("type")) if len(ranked) > 1 else None

        for sc in item.get("standard_charges") or []:
            base = {
                "hospital_id": hospital_id,
                "hospital_name": hospital_name,
                "last_updated_on": last_updated,
                "mrf_version": version,
                "description": desc,
                "setting": _clean(sc.get("setting")),
                "code_1": code_1,
                "code_1_type": code_1_type,
                "code_2": code_2,
                "code_2_type": code_2_type,
                "gross_charge": _money(sc.get("gross_charge")),
                "discounted_cash": _money(sc.get("discounted_cash")),
                "min_charge": _money(sc.get("minimum")),
                "max_charge": _money(sc.get("maximum")),
            }
            payers = sc.get("payers_information") or []
            if not payers:
                n_rows += 1
                yield {
                    **base,
                    "payer_name": None,
                    "plan_name": None,
                    "negotiated_dollar": None,
                    "negotiated_percentage": None,
                    "negotiated_algorithm": None,
                    "methodology": None,
                }
            for p in payers:
                n_rows += 1
                yield {
                    **base,
                    "payer_name": _clean(p.get("payer_name")),
                    "plan_name": _clean(p.get("plan_name")),
                    "negotiated_dollar": _money(p.get("standard_charge_dollar")),
                    "negotiated_percentage": _money(p.get("standard_charge_percentage")),
                    "negotiated_algorithm": _clean(p.get("standard_charge_algorithm")),
                    "methodology": _clean(p.get("methodology")),
                }
    log.info("%s: parsed %d JSON rows", hospital_id, n_rows)


# --------------------------------------------------------------------------
# Dispatch
# --------------------------------------------------------------------------

def parse_mrf(path: Path, hospital_id: str) -> Iterator[dict]:
    """Route a file to the right parser by sniffing content, not extension."""
    head = path.read_bytes()[:4096].lstrip()
    if head.startswith(b"{"):
        return parse_json_mrf(path, hospital_id)
    return parse_tall_csv(path, hospital_id)
