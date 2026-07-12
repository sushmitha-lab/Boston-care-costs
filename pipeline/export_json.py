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

dump("""
    select * from mart_cash_price_comparison
    where billing_code_type in ('CPT','HCPCS','MS-DRG','DRG','APR-DRG')
      and service_key in (
          select service_key from mart_cash_price_comparison
          where cash_price is not null
          group by service_key
          having count(distinct hospital_id) >= 2
      )
""", "comparison")
