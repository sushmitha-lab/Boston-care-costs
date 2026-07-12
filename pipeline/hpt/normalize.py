"""Normalize parsed MRF records into Parquet staging + quality scorecard."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

import polars as pl

log = logging.getLogger("hpt.normalize")

SCHEMA = {
    "hospital_id": pl.Utf8,
    "hospital_name": pl.Utf8,
    "last_updated_on": pl.Utf8,
    "mrf_version": pl.Utf8,
    "description": pl.Utf8,
    "setting": pl.Utf8,
    "code_1": pl.Utf8,
    "code_1_type": pl.Utf8,
    "code_2": pl.Utf8,
    "code_2_type": pl.Utf8,
    "gross_charge": pl.Float64,
    "discounted_cash": pl.Float64,
    "payer_name": pl.Utf8,
    "plan_name": pl.Utf8,
    "negotiated_dollar": pl.Float64,
    "negotiated_percentage": pl.Float64,
    "negotiated_algorithm": pl.Utf8,
    "methodology": pl.Utf8,
    "min_charge": pl.Float64,
    "max_charge": pl.Float64,
}


def records_to_staging(records: Iterable[dict], out_path: Path) -> pl.DataFrame:
    """Write normalized records to Parquet; returns the DataFrame."""
    df = pl.DataFrame(list(records), schema=SCHEMA)

    # Canonicalize: CPT codes uppercase-stripped; settings lowercased.
    df = df.with_columns(
        pl.col("setting").str.to_lowercase(),
        pl.col("code_1_type").str.to_uppercase(),
        pl.col("code_2_type").str.to_uppercase(),
        pl.col("code_1").str.strip_chars(),
        pl.col("code_2").str.strip_chars(),
    )

    # A row is only useful if it has a description AND at least one code.
    before = df.height
    df = df.filter(
        pl.col("description").is_not_null()
        & (pl.col("code_1").is_not_null() | pl.col("code_2").is_not_null())
    )
    dropped = before - df.height
    if dropped:
        log.warning("Dropped %d rows lacking description/code", dropped)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    log.info("Staged %d rows -> %s", df.height, out_path)
    return df


def quality_scorecard(df: pl.DataFrame) -> pl.DataFrame:
    """Per-hospital data-quality metrics. This doubles as an analytical
    output: 'which hospitals publish usable data' is itself a finding."""
    return (
        df.group_by("hospital_id", "hospital_name", "mrf_version")
        .agg(
            pl.len().alias("total_rows"),
            (pl.col("discounted_cash").is_not_null().mean() * 100)
            .round(1)
            .alias("pct_cash_price_present"),
            (pl.col("gross_charge").is_not_null().mean() * 100)
            .round(1)
            .alias("pct_gross_present"),
            (pl.col("negotiated_dollar").is_not_null().mean() * 100)
            .round(1)
            .alias("pct_negotiated_dollar_present"),
            (
                (pl.col("code_1_type").is_in(["CPT", "HCPCS"])
                 | pl.col("code_2_type").is_in(["CPT", "HCPCS"]))
                .mean()
                * 100
            )
            .round(1)
            .alias("pct_rows_with_cpt"),
            pl.col("description").n_unique().alias("distinct_services"),
            pl.col("payer_name").n_unique().alias("distinct_payers"),
        )
        .sort("hospital_id")
    )
