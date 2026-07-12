import { useMemo, useState } from "react";
import comparison from "./data/comparison.json";
import variation from "./data/variation.json";
import cashVsNeg from "./data/cash_vs_negotiated.json";
import hospitals from "./data/hospitals.json";

const fmt = (v) =>
  v == null ? "—" : "$" + Number(v).toLocaleString("en-US", { maximumFractionDigits: 0 });

const HOSPITAL_SHORT = {
  "Massachusetts General Hospital": "Mass General",
  "Brigham and Women's Hospital": "Brigham & Women's",
  "Beth Israel Deaconess Medical Center": "Beth Israel",
};
const short = (n) => HOSPITAL_SHORT[n] || n;

/* Group comparison rows by service */
function useServices() {
  return useMemo(() => {
    const by = new Map();
    for (const r of comparison) {
      if (!by.has(r.service_key)) by.set(r.service_key, { ...r, hospitals: [] });
      by.get(r.service_key).hospitals.push(r);
    }
    return [...by.values()].map((s) => {
      const priced = s.hospitals.filter((h) => h.cash_price != null);
      const prices = priced.map((h) => Number(h.cash_price));
      return {
        ...s,
        priced,
        min: Math.min(...prices),
        max: Math.max(...prices),
        spread: prices.length > 1 ? Math.max(...prices) / Math.min(...prices) : null,
      };
    });
  }, []);
}

/* Signature element: price spread strip */
function SpreadStrip({ svc }) {
  const pad = 90;
  const W = 720, H = 74, y = 40;
  const span = svc.max - svc.min || 1;
  const x = (p) => pad + ((p - svc.min) / span) * (W - pad * 2);
  return (
    <div className="strip" role="img"
      aria-label={`Cash prices from ${fmt(svc.min)} to ${fmt(svc.max)}`}>
      <svg viewBox={`0 0 ${W} ${H}`}>
        <line x1={pad} x2={W - pad} y1={y} y2={y} stroke="var(--hairline)" strokeWidth="2" />
        <text x={pad - 10} y={y + 4} textAnchor="end"
          fontFamily="var(--font-mono)" fontSize="12" fill="var(--ink-soft)">{fmt(svc.min)}</text>
        <text x={W - pad + 10} y={y + 4}
          fontFamily="var(--font-mono)" fontSize="12" fill="var(--ink-soft)">{fmt(svc.max)}</text>
        {svc.priced.map((h, i) => {
          const cx = x(Number(h.cash_price));
          const best = Number(h.cash_price) === svc.min;
          const above = i % 2 === 0;
          return (
            <g key={h.hospital_id}>
              <circle cx={cx} cy={y} r="6"
                fill={best ? "var(--teal)" : "var(--card)"}
                stroke={best ? "var(--teal)" : "var(--ink-soft)"} strokeWidth="2" />
              <text x={cx} y={above ? y - 14 : y + 24} textAnchor="middle"
                fontFamily="var(--font-display)" fontSize="11.5"
                fill={best ? "var(--teal)" : "var(--ink-soft)"}>
                {short(h.hospital_name)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function ServiceCard({ svc }) {
  return (
    <article className="svc">
      <div className="svc-head">
        <h3>{svc.canonical_description}</h3>
        <span className="codepill">{svc.billing_code_type} {svc.billing_code}</span>
        {svc.spread > 1.5 && (
          <span className="spreadnote">{svc.spread.toFixed(1)}× price spread</span>
        )}
      </div>
      {svc.priced.length > 1 && svc.max > svc.min && <SpreadStrip svc={svc} />}
      <div className="rows">
        {[...svc.hospitals]
          .sort((a, b) => (a.cash_price ?? 1e12) - (b.cash_price ?? 1e12))
          .map((h) => (
            <div className="row" key={h.hospital_id}>
              <span className="hosp">{short(h.hospital_name)}</span>
              <span className="lab">cash price</span>
              <span className={"money" + (Number(h.cash_price) === svc.min ? " best" : "")}>
                {fmt(h.cash_price)}
              </span>
            </div>
          ))}
      </div>
    </article>
  );
}

function Compare() {
  const services = useServices();
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const base = needle
      ? services.filter(
          (s) =>
            s.canonical_description.toLowerCase().includes(needle) ||
            String(s.billing_code).includes(needle)
        )
      : [...services].sort((a, b) => (b.spread ?? 0) - (a.spread ?? 0)).slice(0, 6);
    return base.slice(0, 12);
  }, [q, services]);

  return (
    <>
      <div className="hero wrap">
        <h1>The same MRI. Three hospitals. <em>Very different prices.</em></h1>
        <p className="sub">
          Compare cash prices for common procedures across Boston hospitals, straight
          from the machine-readable files hospitals are federally required to publish.
        </p>
        <div className="search">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search a procedure or CPT code — try “MRI” or 70551"
            aria-label="Search procedures"
          />
        </div>
        <div className="chipset">
          {["MRI", "colonoscopy", "blood", "delivery", "emergency"].map((c) => (
            <button key={c} className="chip" onClick={() => setQ(c)}>{c}</button>
          ))}
        </div>
      </div>
      <div className="wrap" style={{ paddingBottom: 50 }}>
        {shown.map((s) => <ServiceCard key={s.service_key} svc={s} />)}
        {!shown.length && (
          <p className="lede">No matching procedure yet. Try a broader term — the pilot
          dataset covers 30 common shoppable services.</p>
        )}
      </div>
    </>
  );
}

function Insights() {
  const topVar = [...variation].sort((a, b) => b.spread_ratio - a.spread_ratio).slice(0, 10);
  const cashWins = cashVsNeg.filter((r) => r.cash_beats_insurance === true || r.cash_beats_insurance === "true");
  return (
    <section className="panel wrap">
      <h2>Where prices diverge most</h2>
      <p className="lede">
        Spread ratio = highest cash price ÷ lowest cash price for the identical
        billing code across hospitals.
      </p>
      <table>
        <thead>
          <tr><th>Procedure</th><th>Code</th><th style={{textAlign:"right"}}>Low</th>
          <th style={{textAlign:"right"}}>High</th><th style={{textAlign:"right"}}>Spread</th></tr>
        </thead>
        <tbody>
          {topVar.map((r) => (
            <tr key={r.service_key}>
              <td>{r.canonical_description}</td>
              <td className="num">{r.billing_code}</td>
              <td className="num">{fmt(r.min_cash_price)}</td>
              <td className="num">{fmt(r.max_cash_price)}</td>
              <td className="num ratio">{Number(r.spread_ratio).toFixed(2)}×</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 style={{ marginTop: 44 }}>When cash beats insurance</h2>
      <p className="lede">
        In {cashWins.length} of {cashVsNeg.length} hospital–procedure pairs, the
        self-pay cash price is lower than the median insurer-negotiated rate at the
        same hospital.
      </p>
      <table>
        <thead>
          <tr><th>Procedure</th><th>Hospital</th>
          <th style={{textAlign:"right"}}>Cash</th>
          <th style={{textAlign:"right"}}>Median negotiated</th>
          <th style={{textAlign:"right"}}>Difference</th></tr>
        </thead>
        <tbody>
          {cashWins.slice(0, 10).map((r, i) => (
            <tr key={i}>
              <td>{r.canonical_description}</td>
              <td>{short(r.hospital_name)}</td>
              <td className="num win">{fmt(r.cash_price)}</td>
              <td className="num">{fmt(r.median_negotiated)}</td>
              <td className="num win">{fmt(r.cash_minus_median_negotiated)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="note">
        Negotiated rates vary by plan; the median across published payer rates is a
        simplification. Always confirm prices with the hospital before care.
      </div>
    </section>
  );
}

function Quality() {
  return (
    <section className="panel wrap">
      <h2>Who publishes usable data?</h2>
      <p className="lede">
        Transparency only works if the files are complete. Each hospital's
        machine-readable file is scored on coverage of the fields patients
        actually need.
      </p>
      <table>
        <thead>
          <tr><th>Hospital</th><th>Rows</th><th>Cash price coverage</th>
          <th style={{textAlign:"right"}}>Negotiated $ coverage</th>
          <th style={{textAlign:"right"}}>Services</th></tr>
        </thead>
        <tbody>
          {hospitals.map((h) => (
            <tr key={h.hospital_id}>
              <td>{short(h.hospital_name)}</td>
              <td className="num">{Number(h.total_rows).toLocaleString()}</td>
              <td>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div className="scorebar" style={{ flex: 1 }}>
                    <i style={{ width: `${h.pct_cash_price_present}%` }} />
                  </div>
                  <span className="num" style={{ fontFamily: "var(--font-mono)", fontSize: 13 }}>
                    {h.pct_cash_price_present}%
                  </span>
                </div>
              </td>
              <td className="num">{h.pct_negotiated_dollar_present}%</td>
              <td className="num">{h.distinct_services}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="note">
        Incomplete files aren't a data bug — they're a compliance finding. CMS can
        fine hospitals whose files omit required standard charges.
      </div>
    </section>
  );
}

function Methodology() {
  return (
    <section className="panel wrap method">
      <h2>Methodology</h2>
      <p>
        Under the federal Hospital Price Transparency rule (45 CFR 180), every US
        hospital must publish a machine-readable file of its standard charges and
        host a <code>cms-hpt.txt</code> pointer file at its domain root. This project
        discovers files through that convention, downloads them monthly, and parses
        both CMS-approved layouts (tall CSV and JSON, schema v2.x/v3.x).
      </p>
      <h3>Pipeline</h3>
      <p>
        Python parsers normalize each file into a common schema, tolerating
        real-world defects: dollar-formatted strings, “N/A” filler, nine-9s
        sentinels, and inconsistent headers. Records are staged as Parquet, modeled
        into a star schema with dbt on DuckDB (dimension, fact, and analytical mart
        layers, with schema and range tests), and exported as static JSON for this
        site. A scheduled GitHub Actions job refreshes the data monthly.
      </p>
      <h3>Limitations</h3>
      <p>
        Published prices are hospital-reported and may lag reality; negotiated rates
        vary by plan and are summarized as medians; professional fees (the doctor's
        bill) are typically excluded from facility files. This site is an
        informational tool, not a quote.
      </p>

    </section>
  );
}

const TABS = [
  ["Compare", Compare],
  ["Insights", Insights],
  ["Data quality", Quality],
  ["Methodology", Methodology],
];

export default function App() {
  const [tab, setTab] = useState(0);
  const Active = TABS[tab][1];
  return (
    <>
      <header>
        <div className="wrap masthead">
          <div className="brand"><span className="pulse">▸</span> Boston Care Costs</div>
          <div className="tagline">Hospital price transparency, made legible</div>
        </div>
        <div className="wrap">
          <nav aria-label="Sections">
            {TABS.map(([name], i) => (
              <button key={name} className={i === tab ? "active" : ""} onClick={() => setTab(i)}>
                {name}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main><Active /></main>
      <footer>
        <div className="wrap">
          Built from CMS-mandated machine-readable files · Sample data pending live
          ingestion · Not medical or financial advice ·{" "}
          <a href="https://github.com/sushmitha-lab" style={{ color: "var(--teal)" }}>
            github.com/sushmitha-lab
          </a>
        </div>
      </footer>
    </>
  );
}
