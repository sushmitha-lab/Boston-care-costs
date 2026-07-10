"""Export dbt marts to JSON for the React app (Vercel static data)."""
import json
from pathlib import Path
import os
import duckdb

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "src" / "data"
OUT.mkdir(parents=True, exist_ok=True)

os.chdir(ROOT / "pipeline" / "dbt_project")
con = duckdb.connect(str(ROOT / "data" / "hpt.duckdb"), read_only=True)

def dump(query: str, name: str):
    rows = [dict(zip([d[0] for d in con.description], r))
            for r in con.execute(query).fetchall()]
    (OUT / f"{name}.json").write_text(json.dumps(rows, default=str))
    print(f"{name}: {len(rows)} rows")

dump("select * from mart_cash_price_comparison", "comparison")
dump("select * from mart_price_variation", "variation")
dump("select * from mart_cash_vs_negotiated", "cash_vs_negotiated")
dump("""select h.*, q.* exclude (hospital_id, hospital_name, mrf_version)
        from dim_hospital h
        join read_csv_auto('../../data/staging/quality_scorecard.csv') q
        using (hospital_id)""", "hospitals")
