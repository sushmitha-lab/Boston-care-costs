"""Generate realistic SAMPLE MRFs for local development and CI.

Prices are synthetic (seeded random around plausible magnitudes) — clearly
marked as sample data. Structure follows the official CMS v3.0.0 templates,
with deliberate real-world defects injected so the parser and quality
scorecard have something honest to chew on:

  - mgh   -> JSON v3, mostly clean
  - bwh   -> tall CSV v3, clean-ish but prices formatted as "$1,234.00"
  - bidmc -> tall CSV, non-compliant: "N/A" filler, blank cash prices,
             mixed-case headers with stray spaces, nine-9s sentinels

Run: python make_sample_data.py
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

random.seed(42)

# 30 common shoppable services: (description, CPT/DRG code, code type, setting, base price)
SERVICES = [
    ("MRI brain without contrast", "70551", "CPT", "outpatient", 1800),
    ("MRI lumbar spine without contrast", "72148", "CPT", "outpatient", 1700),
    ("CT head without contrast", "70450", "CPT", "outpatient", 1100),
    ("CT abdomen and pelvis with contrast", "74177", "CPT", "outpatient", 2400),
    ("X-ray chest 2 views", "71046", "CPT", "outpatient", 320),
    ("Ultrasound abdominal complete", "76700", "CPT", "outpatient", 650),
    ("Mammography screening bilateral", "77067", "CPT", "outpatient", 420),
    ("Colonoscopy diagnostic", "45378", "CPT", "outpatient", 2900),
    ("Upper GI endoscopy diagnostic", "43235", "CPT", "outpatient", 2500),
    ("Basic metabolic panel", "80048", "CPT", "outpatient", 95),
    ("Comprehensive metabolic panel", "80053", "CPT", "outpatient", 130),
    ("Complete blood count with differential", "85025", "CPT", "outpatient", 85),
    ("Lipid panel", "80061", "CPT", "outpatient", 110),
    ("Hemoglobin A1c", "83036", "CPT", "outpatient", 90),
    ("TSH thyroid stimulating hormone", "84443", "CPT", "outpatient", 120),
    ("Urinalysis automated with microscopy", "81001", "CPT", "outpatient", 55),
    ("Office visit established patient level 3", "99213", "CPT", "outpatient", 240),
    ("Office visit established patient level 4", "99214", "CPT", "outpatient", 350),
    ("Emergency department visit level 4", "99284", "CPT", "outpatient", 1450),
    ("Emergency department visit level 5", "99285", "CPT", "outpatient", 2300),
    ("Physical therapy therapeutic exercise 15 min", "97110", "CPT", "outpatient", 160),
    ("Echocardiogram transthoracic complete", "93306", "CPT", "outpatient", 1500),
    ("Electrocardiogram complete", "93000", "CPT", "outpatient", 190),
    ("Cardiac stress test treadmill", "93015", "CPT", "outpatient", 900),
    ("Sleep study polysomnography", "95810", "CPT", "outpatient", 3200),
    ("Major joint replacement lower extremity w/o MCC", "470", "MS-DRG", "inpatient", 42000),
    ("Cesarean section w/o CC/MCC", "788", "MS-DRG", "inpatient", 18500),
    ("Vaginal delivery w/o complicating diagnoses", "807", "MS-DRG", "inpatient", 14500),
    ("Laparoscopic cholecystectomy w/o CC/MCC", "419", "MS-DRG", "inpatient", 21000),
    ("Spinal fusion except cervical w/o MCC", "460", "MS-DRG", "inpatient", 68000),
]

PAYERS = [
    ("Blue Cross Blue Shield of MA", "PPO"),
    ("Blue Cross Blue Shield of MA", "HMO Blue"),
    ("Harvard Pilgrim Health Care", "HMO"),
    ("Tufts Health Plan", "PPO"),
    ("UnitedHealthcare", "Choice Plus"),
    ("Aetna", "Open Access"),
]

ATTESTATION = (
    "To the best of its knowledge and belief, this hospital has included all "
    "applicable standard charge information in accordance with the requirements "
    "of 45 CFR 180.50 [SAMPLE DATA FOR DEVELOPMENT — NOT REAL PRICES]."
)

TALL_HEADERS = [
    "description", "code | 1", "code | 1 | type", "code | 2", "code | 2 | type",
    "setting", "drug_unit_of_measurement", "drug_type_of_measurement",
    "standard_charge | gross", "standard_charge | discounted_cash",
    "payer_name", "plan_name", "modifiers",
    "standard_charge | negotiated_dollar", "standard_charge | negotiated_percentage",
    "standard_charge | negotiated_algorithm", "estimated_amount",
    "standard_charge | min", "standard_charge | max",
    "standard_charge | methodology", "additional_generic_notes",
]


def hospital_prices(multiplier: float):
    """Yield per-service price structure for one hospital."""
    for desc, code, code_type, setting, base in SERVICES:
        gross = round(base * multiplier * random.uniform(1.6, 2.6), 2)
        cash = round(gross * random.uniform(0.35, 0.65), 2)
        rates = [round(gross * random.uniform(0.25, 0.55), 2) for _ in PAYERS]
        yield desc, code, code_type, setting, gross, cash, rates


def write_mgh_json():
    items = []
    for desc, code, code_type, setting, gross, cash, rates in hospital_prices(1.25):
        items.append({
            "description": desc,
            "code_information": [{"code": code, "type": code_type}],
            "standard_charges": [{
                "setting": setting,
                "gross_charge": gross,
                "discounted_cash": cash,
                "minimum": min(rates),
                "maximum": max(rates),
                "payers_information": [
                    {"payer_name": p, "plan_name": pl, "methodology": "fee schedule",
                     "standard_charge_dollar": r}
                    for (p, pl), r in zip(PAYERS, rates)
                ],
            }],
        })
    doc = {
        "hospital_name": "Massachusetts General Hospital [SAMPLE]",
        "last_updated_on": date.today().isoformat(),
        "version": "3.0.0",
        "hospital_address": ["55 Fruit Street, Boston, MA 02114"],
        "license_information": {"state": "MA", "license_number": "SAMPLE-0001"},
        "attestation": {"attestation": ATTESTATION, "confirm_attestation": True,
                        "attester_name": "Sample Attester"},
        "standard_charge_information": items,
    }
    out = RAW / "mgh" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    (out / "042103558_massachusetts-general-hospital_standardcharges.json").write_text(
        json.dumps(doc, indent=1)
    )


def _write_tall(path: Path, hospital_name: str, rows: list[list]):
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hospital_name", "last_updated_on", "version", "hospital_location",
                    "hospital_address", "license_number | MA", "attestation"]
                   + [""] * (len(TALL_HEADERS) - 7))
        w.writerow([hospital_name, date.today().isoformat(), "3.0.0", hospital_name,
                    "Boston, MA", "SAMPLE-000X", "TRUE"]
                   + [""] * (len(TALL_HEADERS) - 7))
        w.writerow(TALL_HEADERS)
        w.writerows(rows)


def write_bwh_csv():
    """Clean structure, but prices formatted as '$1,234.00' (spec violation)."""
    rows = []
    for desc, code, code_type, setting, gross, cash, rates in hospital_prices(1.15):
        for (payer, plan), rate in zip(PAYERS, rates):
            rows.append([
                desc, code, code_type, "", "", setting, "", "",
                f"${gross:,.2f}", f"${cash:,.2f}",
                payer, plan, "", f"${rate:,.2f}", "", "", "",
                f"${min(rates):,.2f}", f"${max(rates):,.2f}", "fee schedule", "",
            ])
    out = RAW / "bwh" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    _write_tall(out / "042103559_brigham-and-womens_standardcharges.csv",
                "Brigham and Women's Hospital [SAMPLE]", rows)


def write_bidmc_csv():
    """Non-compliant on purpose: N/A filler, missing cash prices on ~40% of
    services, nine-9s sentinels, stray header casing/whitespace."""
    rows = []
    for desc, code, code_type, setting, gross, cash, rates in hospital_prices(0.95):
        hide_cash = random.random() < 0.4
        for (payer, plan), rate in zip(PAYERS, rates):
            rows.append([
                desc, code, code_type, "N/A", "N/A", setting.upper(), "", "",
                gross, ("" if hide_cash else cash),
                payer, plan, "N/A",
                (999999999 if random.random() < 0.1 else rate),
                "", "", "N/A",
                min(rates), max(rates), "fee schedule", "N/A",
            ])
    out = RAW / "bidmc" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "042103560_beth-israel-deaconess_standardcharges.csv"
    # Sloppy headers: mixed case + stray spaces (parser must normalize)
    sloppy = [h.replace("standard_charge", "Standard_Charge ") for h in TALL_HEADERS]
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Hospital_Name", "Last_Updated_On", "Version", "Hospital_Location",
                    "Hospital_Address", "License_Number | MA", "Attestation"]
                   + [""] * (len(sloppy) - 7))
        w.writerow(["Beth Israel Deaconess Medical Center [SAMPLE]",
                    date.today().isoformat(), "3.0.0", "BIDMC", "Boston, MA",
                    "SAMPLE-000Y", "TRUE"] + [""] * (len(sloppy) - 7))
        w.writerow(sloppy)
        w.writerows(rows)


if __name__ == "__main__":
    write_mgh_json()
    write_bwh_csv()
    write_bidmc_csv()
    print("Sample MRFs written under", RAW)
