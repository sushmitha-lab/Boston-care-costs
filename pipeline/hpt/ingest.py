"""Discovery + download of hospital machine-readable files (MRFs).

Since July 2024, 45 CFR 180 requires every hospital to host a plain-text
file at https://<domain>/cms-hpt.txt containing, among other fields, a
`mrf-url:` line pointing to the machine-readable standard-charges file.
We use that convention for zero-config discovery.
"""

from __future__ import annotations

import gzip
import io
import logging
import re
import zipfile
from datetime import date
from pathlib import Path

import requests

log = logging.getLogger("hpt.ingest")

USER_AGENT = (
    "BostonHPT-Pipeline/0.1 (portfolio research project; "
    "contact: see repository README)"
)
TIMEOUT = 120


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def discover_mrf_url(domain: str, session: requests.Session | None = None) -> str | None:
    """Fetch cms-hpt.txt from a hospital domain and extract the MRF URL."""
    session = session or _session()
    for scheme_host in (f"https://{domain}", f"https://www.{domain}"):
        url = f"{scheme_host}/cms-hpt.txt"
        try:
            r = session.get(url, timeout=TIMEOUT)
            if r.status_code != 200:
                continue
            m = re.search(r"^mrf-url:\s*(\S+)", r.text, flags=re.M | re.I)
            if m:
                log.info("Discovered MRF for %s: %s", domain, m.group(1))
                return m.group(1)
        except requests.RequestException as exc:
            log.warning("cms-hpt.txt fetch failed for %s: %s", url, exc)
    return None


def download_mrf(url: str, dest_dir: Path, hospital_id: str) -> Path:
    """Download an MRF, decompressing .gz/.zip transparently.

    Files are versioned by download date so monthly re-runs never
    overwrite history: data/raw/<hospital_id>/<YYYY-MM-DD>/<filename>
    """
    session = _session()
    out_dir = dest_dir / hospital_id / date.today().isoformat()
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Downloading %s", url)
    r = session.get(url, timeout=TIMEOUT, stream=True)
    r.raise_for_status()
    content = r.content

    fname = url.split("/")[-1].split("?")[0] or f"{hospital_id}_standardcharges"

    if fname.endswith(".gz"):
        content = gzip.decompress(content)
        fname = fname[: -len(".gz")]
    elif fname.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            inner = next(
                n for n in zf.namelist() if n.lower().endswith((".csv", ".json"))
            )
            content = zf.read(inner)
            fname = Path(inner).name

    out_path = out_dir / fname
    out_path.write_bytes(content)
    log.info("Saved %s (%.1f MB)", out_path, len(content) / 1e6)
    return out_path
