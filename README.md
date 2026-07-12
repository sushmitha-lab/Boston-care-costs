# Boston Care Costs — Hospital Price Transparency Pipeline

Compare cash prices for common procedures across Boston hospitals, built from the
machine-readable files (MRFs) every US hospital is federally required to publish
under 45 CFR 180.

**Live app:** [_add Vercel URL after deploy_](https://boston-care-costs.vercel.app/) · **Stack:** Python · Polars · DuckDB · dbt · GitHub Actions · React (Vite) · Vercel

## Why this exists

Hospitals must publish standard charges, but the files are large, inconsistent,
and unread. This project turns them into something a patient can actually use —
and measures which hospitals publish usable data at all.

## Architecture

```
cms-hpt.txt discovery ─► download (versioned by date)
        │
        ▼
Python parsers (tall CSV + JSON, schema v2.x/v3.x)
  · tolerant of $-formatted prices, "N/A" filler, nine-9s sentinels
        │
        ▼
Parquet staging (Polars) ─► data-quality scorecard
        │
        ▼
dbt on DuckDB
  staging views ─► dim_hospital / dim_service / fct_standard_charges
                ─► marts: cash comparison · price variation · cash-vs-negotiated
  8 schema + range tests
        │
        ▼
JSON export ─► React app (Vite) on Vercel
GitHub Actions re-runs the whole thing monthly
```

## Repository layout

```
pipeline/            Python package + dbt project
  hpt/               ingest, parsers, normalize modules
  run_pipeline.py    CLI: --download to discover+fetch, else parse local files
  make_sample_data.py  generates realistic messy sample MRFs (CI/dev)
  dbt_project/       models, tests, duckdb profile
web/                 React app (deploy this directory on Vercel)
data/                raw (gitignored) · staging · duckdb
.github/workflows/   monthly refresh cron
```

## Run it locally

```bash
# 1. Pipeline
pip install -r pipeline/requirements.txt
python pipeline/make_sample_data.py          # or: run_pipeline.py --download
python pipeline/run_pipeline.py

# 2. Models + tests
cd pipeline/dbt_project
DBT_PROFILES_DIR=. dbt deps && DBT_PROFILES_DIR=. dbt build

# 3. Export + app
cd ../.. && python pipeline/export_json.py
cd web && npm install && npm run dev
```

## Switching from sample to real data

1. `python pipeline/run_pipeline.py --download` — discovers each hospital's MRF
   via its mandated `cms-hpt.txt`. If discovery fails for a hospital, find the
   file manually (search "<hospital> standard charges machine readable") and set
   `mrf_url` in `pipeline/hospitals.yaml`.
2. Re-run steps 2–3 above. Everything downstream is format-agnostic.
3. Real MGB files are multi-GB — the parsers stream CSVs row-by-row, but for the
   JSON format on very large files, consider swapping `json.load` for `ijson`.
4. Remove the sample-data notice in `web/src/App.jsx` (Methodology section).

## Deploy (Vercel)

- Import the repo → set **Root Directory = `web`** → framework auto-detects Vite.
- Data ships inside the bundle as static JSON; the monthly Action commits fresh
  data, which triggers an automatic redeploy.

## Data quality as a finding

The pipeline scores every hospital's file on coverage of cash prices, negotiated
dollars, and CPT codes. Incomplete files are surfaced in the app — compliance
itself is one of the analytical outputs.

## Honest limitations

Prices are hospital-reported and may lag reality. Negotiated rates vary by plan
and are summarized as medians. Facility files usually exclude professional fees.
This is an informational tool, not a quote.

## Data sources & etiquette

Hospital MRFs are public by federal mandate (45 CFR 180). The downloader
identifies itself with a descriptive user-agent and fetches each file at most
monthly. CMS schema reference: github.com/CMSgov/hospital-price-transparency.
