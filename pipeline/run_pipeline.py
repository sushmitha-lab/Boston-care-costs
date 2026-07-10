"""Boston HPT pipeline orchestrator.

Usage:
    python run_pipeline.py --local data/raw            # parse already-downloaded files
    python run_pipeline.py --download                  # discover via cms-hpt.txt + download
    python run_pipeline.py --download --hospital mgh   # single hospital

Outputs:
    data/staging/standard_charges.parquet
    data/staging/quality_scorecard.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from itertools import chain
from pathlib import Path

import polars as pl
import yaml

sys.path.insert(0, str(Path(__file__).parent))
from hpt.ingest import discover_mrf_url, download_mrf  # noqa: E402
from hpt.normalize import quality_scorecard, records_to_staging  # noqa: E402
from hpt.parsers import parse_mrf  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("hpt.pipeline")

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
STAGING = ROOT / "data" / "staging"


def load_registry() -> list[dict]:
    with open(Path(__file__).parent / "hospitals.yaml") as f:
        return yaml.safe_load(f)["hospitals"]


def latest_file_for(hospital_id: str) -> Path | None:
    """Most recent downloaded MRF for a hospital (raw/<id>/<date>/file)."""
    base = RAW / hospital_id
    if not base.exists():
        return None
    dated = sorted((d for d in base.iterdir() if d.is_dir()), reverse=True)
    for d in dated:
        files = [p for p in d.iterdir() if p.suffix.lower() in {".csv", ".json"}]
        if files:
            return max(files, key=lambda p: p.stat().st_size)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true", help="discover + download MRFs")
    ap.add_argument("--hospital", help="limit to a single hospital id")
    args = ap.parse_args()

    hospitals = load_registry()
    if args.hospital:
        hospitals = [h for h in hospitals if h["id"] == args.hospital]
        if not hospitals:
            sys.exit(f"Unknown hospital id: {args.hospital}")

    if args.download:
        for h in hospitals:
            url = h.get("mrf_url") or discover_mrf_url(h["domain"])
            if not url:
                log.error("No MRF URL found for %s — set mrf_url in hospitals.yaml", h["id"])
                continue
            try:
                download_mrf(url, RAW, h["id"])
            except Exception as exc:  # noqa: BLE001 — keep going per-hospital
                log.error("Download failed for %s: %s", h["id"], exc)

    streams = []
    for h in hospitals:
        path = latest_file_for(h["id"])
        if not path:
            log.warning("No raw file for %s — skipping", h["id"])
            continue
        log.info("Parsing %s (%s)", h["id"], path.name)
        streams.append(parse_mrf(path, h["id"]))

    if not streams:
        sys.exit("Nothing to parse. Run with --download or place files under data/raw/<id>/<date>/")

    df = records_to_staging(chain.from_iterable(streams), STAGING / "standard_charges.parquet")

    scorecard = quality_scorecard(df)
    STAGING.mkdir(parents=True, exist_ok=True)
    scorecard.write_csv(STAGING / "quality_scorecard.csv")
    with pl.Config(tbl_cols=-1, tbl_width_chars=200):
        print("\n=== Data Quality Scorecard ===")
        print(scorecard)


if __name__ == "__main__":
    main()
