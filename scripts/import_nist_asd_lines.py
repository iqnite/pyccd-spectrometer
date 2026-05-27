#!/usr/bin/env python3
"""Download and normalize NIST ASD line data into the local JSON catalog format.

This script queries the NIST Atomic Spectra Database (ASD) "Lines" endpoint and
writes a JSON catalog that `spectrometer.line_matching.load_line_catalog()` can
load.

Typical usage (generate NIST catalog for the elements currently present in the
legacy element list, neutral stage, visible range):

    python3 scripts/import_nist_asd_lines.py --from-legacy --low-nm 350 --upp-nm 750 --output nist_line_catalog.json

You can also provide explicit spectra (NIST syntax):

    python3 scripts/import_nist_asd_lines.py --spectra "H I;He I;Fe I" --low-nm 350 --upp-nm 750 --output nist_line_catalog.json

Notes:
- NIST may rate-limit or change fields; this script keeps the query close to the
  web form defaults to avoid server-side errors.
- Output is designed for offline use inside the app (and PyInstaller bundles).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


NIST_LINES_ENDPOINT = "https://physics.nist.gov/cgi-bin/ASD/lines1.pl"

_NUM_RE = re.compile(r"[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _coerce_floatish(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # remove common wrappers
    s = s.strip("[](){}")
    m = _NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None


def _int_to_roman(n: int) -> str:
    # Enough for ASD ion stages in practical ranges
    if n <= 0:
        return str(n)
    mapping = [
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    ]
    out = []
    x = n
    for v, sym in mapping:
        while x >= v:
            out.append(sym)
            x -= v
    return "".join(out)


def _parse_spectrum_hint(spectrum: str) -> tuple[str | None, str | None]:
    """Best-effort parse of "Fe I" -> ("Fe", "I")."""
    parts = spectrum.strip().split()
    if not parts:
        return (None, None)
    element = parts[0]
    ion = None
    if len(parts) >= 2:
        ion = parts[1]
    return (element, ion)


def _default_query_params(
    *,
    spectra: str,
    low_w: float | None,
    upp_w: float | None,
    unit: str = "1",  # 1 = nm
    fmt: str = "3",  # 3 = tab-delimited
    include_forbidden: bool = True,
) -> dict[str, str]:
    """Parameters modeled after the NIST Lines web form defaults.

    NIST's CGI currently errors (500) when some form fields are absent.
    Keeping defaults explicit avoids those server-side issues.
    """

    params: dict[str, str] = {
        "spectra": spectra,
        "output_type": "0",  # wavelength
        "low_w": "" if low_w is None else str(low_w),
        "upp_w": "" if upp_w is None else str(upp_w),
        "unit": unit,
        "submit": "Retrieve Data",
        "de": "0",
        "plot_out": "0",
        "I_scale_type": "1",
        "format": fmt,
        "line_out": "0",  # all lines
        "remove_js": "on",
        "en_unit": "0",  # cm-1
        "output": "0",  # entirety
        "bibrefs": "1",
        "page_size": "15",
        "show_obs_wl": "1",
        "show_calc_wl": "1",
        "unc_out": "1",
        "order_out": "0",
        "max_low_enrg": "",
        "show_av": "2",
        "max_upp_enrg": "",
        "tsb_value": "0",  # Aki
        "min_str": "",
        "A_out": "0",
        "intens_out": "on",
        "max_str": "",
        "allowed_out": "1",
        "min_accur": "",
        "min_intens": "",
        "conf_out": "on",
        "term_out": "on",
        "enrg_out": "on",
        "J_out": "on",
    }

    if include_forbidden:
        params["forbid_out"] = "1"

    return params


def _fetch_lines_text(url: str, *, timeout_s: float = 30.0) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "pyccd-spectrometer (offline catalog generator)",
            "Accept": "text/plain,*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_s) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def _parse_tab_delimited(text: str) -> tuple[list[str], list[list[str]]]:
    reader = csv.reader(io.StringIO(text), delimiter="\t")
    rows = [row for row in reader if row]
    if not rows:
        return ([], [])

    header = [h.strip() for h in rows[0]]
    data = rows[1:]

    # Drop trailing empty header columns
    while header and not header[-1]:
        header.pop()
        for r in data:
            if r:
                r.pop() if len(r) > len(header) else None

    return (header, data)


def _row_to_record(
    header: list[str],
    row: list[str],
    *,
    element_hint: str | None,
    ion_hint: str | None,
    source: str,
) -> tuple[str | None, dict[str, Any] | None]:
    # Build map
    values: dict[str, str] = {}
    for i, key in enumerate(header):
        if not key:
            continue
        values[key] = row[i].strip() if i < len(row) else ""

    element = values.get("element") or element_hint

    ion_stage: str | None = None
    sp_num = values.get("sp_num")
    if sp_num:
        sp = _coerce_floatish(sp_num)
        if sp is not None:
            try:
                ion_stage = _int_to_roman(int(sp))
            except Exception:
                ion_stage = str(sp_num)
    else:
        ion_stage = ion_hint

    # Wavelength columns vary depending on air/vacuum selection
    obs_nm = (
        values.get("obs_wl_air(nm)")
        or values.get("obs_wl_vac(nm)")
        or values.get("obs_wl(nm)")
        or ""
    )
    ritz_nm = (
        values.get("ritz_wl_air(nm)")
        or values.get("ritz_wl_vac(nm)")
        or values.get("ritz_wl(nm)")
        or ""
    )

    unc_obs = values.get("unc_obs_wl") or ""
    unc_ritz = values.get("unc_ritz_wl") or ""

    obs_val = _coerce_floatish(obs_nm)
    ritz_val = _coerce_floatish(ritz_nm)
    unc_obs_val = _coerce_floatish(unc_obs)
    unc_ritz_val = _coerce_floatish(unc_ritz)

    intens_val = _coerce_floatish(values.get("intens") or "")
    aki_val = _coerce_floatish(values.get("Aki(s^-1)") or "")

    line_type = (values.get("Type") or "").strip() or None

    match_wl = ritz_val if ritz_val is not None else obs_val
    if match_wl is None:
        return (element, None)

    # Choose uncertainty consistent with match wavelength preference
    uncertainty_nm = None
    if ritz_val is not None:
        uncertainty_nm = unc_ritz_val
    else:
        uncertainty_nm = unc_obs_val

    rec: dict[str, Any] = {
        "ion_stage": ion_stage,
        "wavelength_nm": float(match_wl),
        "observed_wavelength_nm": obs_val,
        "ritz_wavelength_nm": ritz_val,
        "observed_uncertainty_nm": unc_obs_val,
        "ritz_uncertainty_nm": unc_ritz_val,
        "uncertainty_nm": uncertainty_nm,
        "relative_intensity": intens_val,
        "aki": aki_val,
        "line_type": line_type,
        "source": source,
    }

    # Keep only minimal extra metadata (optional but useful later)
    if "Acc" in values and values.get("Acc"):
        rec["accuracy"] = values.get("Acc")
    if "tp_ref" in values and values.get("tp_ref"):
        rec["tp_ref"] = values.get("tp_ref")
    if "line_ref" in values and values.get("line_ref"):
        rec["line_ref"] = values.get("line_ref")

    return (element, rec)


def _iter_spectra(args: argparse.Namespace) -> list[str]:
    if args.spectra:
        # allow both repeated args and a single semicolon-separated string
        out: list[str] = []
        for item in args.spectra:
            parts = [p.strip() for p in re.split(r"[;\n]+", item) if p.strip()]
            out.extend(parts)
        return out

    if args.elements:
        stages = args.stages or ["I"]
        spectra: list[str] = []
        for el in args.elements:
            for st in stages:
                spectra.append(f"{el} {st}")
        return spectra

    if args.from_legacy:
        legacy_path = _repo_root() / "element_emission_lines.json"
        try:
            data = json.loads(legacy_path.read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit(f"Failed to read legacy file {legacy_path}: {e}")
        if not isinstance(data, dict):
            raise SystemExit(f"Legacy file {legacy_path} is not a dict")
        elements = [str(k) for k in data.keys()]
        stages = args.stages or ["I"]
        return [f"{el} {stages[0]}" for el in elements]

    raise SystemExit("Provide --spectra or --elements or --from-legacy")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--spectra",
        action="append",
        help="NIST spectra string(s), e.g. 'H I;He I;Fe I' (repeatable)",
    )
    parser.add_argument(
        "--elements",
        nargs="+",
        help="Element symbols (used with --stages to build NIST spectra like 'Fe I')",
    )
    parser.add_argument(
        "--stages",
        nargs="+",
        default=["I"],
        help="Ion stages (Roman numerals). Default: I",
    )
    parser.add_argument(
        "--from-legacy",
        action="store_true",
        help="Use keys from element_emission_lines.json as element list (stage I by default)",
    )
    parser.add_argument("--low-nm", type=float, default=350.0)
    parser.add_argument("--upp-nm", type=float, default=750.0)
    parser.add_argument(
        "--include-forbidden",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Include forbidden lines (M1/E2/etc). Default: true",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Seconds to sleep between requests (polite). Default: 0.2",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout (seconds). Default: 30",
    )
    parser.add_argument(
        "--output",
        default=str(_repo_root() / "nist_line_catalog.json"),
        help="Output JSON file path (default: repo-root/nist_line_catalog.json)",
    )
    parser.add_argument(
        "--compact",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Write compact JSON (default: true)",
    )

    args = parser.parse_args(argv)

    spectra_list = _iter_spectra(args)

    out_path = Path(args.output).expanduser().resolve()

    source = "NIST ASD"
    meta = {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": NIST_LINES_ENDPOINT,
        "wavelength_range_nm": [args.low_nm, args.upp_nm],
        "include_forbidden": bool(args.include_forbidden),
        "spectra": spectra_list,
        "schema": "pyccd-spectrometer/nist-line-catalog/v1",
    }

    catalog: dict[str, list[dict[str, Any]]] = {"_meta": meta}  # meta is ignored by loader

    for i, spectrum in enumerate(spectra_list, 1):
        element_hint, ion_hint = _parse_spectrum_hint(spectrum)

        params = _default_query_params(
            spectra=spectrum,
            low_w=float(args.low_nm),
            upp_w=float(args.upp_nm),
            include_forbidden=bool(args.include_forbidden),
        )
        url = NIST_LINES_ENDPOINT + "?" + urllib.parse.urlencode(params)

        print(f"[{i}/{len(spectra_list)}] Fetching {spectrum} ...")
        try:
            text = _fetch_lines_text(url, timeout_s=float(args.timeout))
        except Exception as e:
            print(f"  ERROR: request failed for {spectrum}: {e}")
            continue

        if text.lstrip().startswith("<"):
            # HTML error
            print(f"  ERROR: NIST returned HTML for {spectrum} (query failed)")
            continue

        header, rows = _parse_tab_delimited(text)
        if not header:
            print(f"  WARNING: no data for {spectrum}")
            continue

        parsed_count = 0
        kept_count = 0
        for row in rows:
            parsed_count += 1
            element, rec = _row_to_record(
                header,
                row,
                element_hint=element_hint,
                ion_hint=ion_hint,
                source=source,
            )
            if rec is None or element is None:
                continue
            catalog.setdefault(element, []).append(rec)
            kept_count += 1

        print(f"  Parsed {parsed_count} rows, kept {kept_count} lines")

        # Be polite to NIST
        if args.sleep and i != len(spectra_list):
            time.sleep(float(args.sleep))

    # Sort records by wavelength for stable output
    for k, v in list(catalog.items()):
        if k == "_meta":
            continue
        try:
            v.sort(key=lambda r: float(r.get("wavelength_nm", 0.0)))
        except Exception:
            pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if args.compact:
        json_text = json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))
    else:
        json_text = json.dumps(catalog, ensure_ascii=False, indent=2)

    out_path.write_text(json_text, encoding="utf-8")

    # Quick summary
    total_lines = sum(len(v) for k, v in catalog.items() if k != "_meta")
    print(f"\nWrote {out_path} ({total_lines} total lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
