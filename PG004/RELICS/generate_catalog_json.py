#!/usr/bin/env python3
"""Build compact, pre-crossmatched JSON database for client-side search."""

import csv
import json
import math
import time
from pathlib import Path
import numpy as np

DEFAULT_RA_OFFSET_ARCSEC = 0.536463
DEFAULT_DEC_OFFSET_ARCSEC = -0.001390

def read_relics_cat(path="plckg004-19.cat"):
    lines = Path(path).read_text().splitlines()
    header_line = next(l for l in lines if l.startswith("##  id"))
    fields = header_line[2:].split()
    rows = []
    for l in lines:
        if not l or l.startswith("#"): continue
        vals = l.split()
        if len(vals) == len(fields):
            rows.append(dict(zip(fields, vals)))
    return rows

def read_jwst_csv(path="pg004_aphot_cut_wzphots.csv"):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def clean_num(val, digits=3):
    try:
        f = float(val)
        if math.isnan(f) or not math.isfinite(f):
            return None
        return round(f, digits)
    except (TypeError, ValueError):
        return None

def main():
    t0 = time.time()
    relics_list = read_relics_cat()
    jwst_list = read_jwst_csv()

    # Pre-calculate nearest match for all JWST and RELICS
    r_ra = np.array([float(r["RA"]) for r in relics_list])
    r_dec = np.array([float(r["Dec"]) for r in relics_list])
    r_dec_shifted = r_dec + DEFAULT_DEC_OFFSET_ARCSEC / 3600.0
    r_ra_shifted = r_ra + DEFAULT_RA_OFFSET_ARCSEC / (3600.0 * np.cos(np.radians(r_dec_shifted)))

    j_ra = np.array([float(j["ra"]) for j in jwst_list])
    j_dec = np.array([float(j["dec"]) for j in jwst_list])

    cos_dec = np.cos(np.radians(-33.508))
    r_x = r_ra_shifted * cos_dec * 3600.0
    r_y = r_dec_shifted * 3600.0
    j_x = j_ra * cos_dec * 3600.0
    j_y = j_dec * 3600.0

    # Match JWST -> nearest RELICS
    chunk_size = 2000
    j2r_idx = np.zeros(len(j_x), dtype=int)
    j2r_dist = np.zeros(len(j_x), dtype=float)
    for i in range(0, len(j_x), chunk_size):
        dx = j_x[i:i+chunk_size, None] - r_x[None, :]
        dy = j_y[i:i+chunk_size, None] - r_y[None, :]
        dist_sq = dx*dx + dy*dy
        min_idx = np.argmin(dist_sq, axis=1)
        j2r_idx[i:i+chunk_size] = min_idx
        j2r_dist[i:i+chunk_size] = np.sqrt(dist_sq[np.arange(len(min_idx)), min_idx])

    # Match RELICS -> nearest JWST
    r2j_idx = np.zeros(len(r_x), dtype=int)
    r2j_dist = np.zeros(len(r_x), dtype=float)
    for i in range(0, len(r_x), chunk_size):
        dx = r_x[i:i+chunk_size, None] - j_x[None, :]
        dy = r_y[i:i+chunk_size, None] - j_y[None, :]
        dist_sq = dx*dx + dy*dy
        min_idx = np.argmin(dist_sq, axis=1)
        r2j_idx[i:i+chunk_size] = min_idx
        r2j_dist[i:i+chunk_size] = np.sqrt(dist_sq[np.arange(len(min_idx)), min_idx])

    # Build compact dictionary
    # Relics lookup map
    relics_compact = {}
    for idx, r in enumerate(relics_list):
        rid = str(r["id"])
        nearest_j = jwst_list[r2j_idx[idx]]
        relics_compact[rid] = {
            "ra": clean_num(r["RA"], 6),
            "dec": clean_num(r["Dec"], 6),
            "zb": clean_num(r.get("zb"), 3),
            "zbmin": clean_num(r.get("zbmin"), 3),
            "zbmax": clean_num(r.get("zbmax"), 3),
            "stel": clean_num(r.get("stel"), 2),
            "odds": clean_num(r.get("odds"), 2),
            "mag": clean_num(r.get("mag_auto"), 2) or clean_num(r.get("bright_mag"), 2),
            "match_j": str(nearest_j["id"]),
            "sep": clean_num(r2j_dist[idx], 3),
        }

    # JWST lookup map
    jwst_compact = {}
    for idx, j in enumerate(jwst_list):
        jid = str(j["id"])
        nearest_r = relics_list[j2r_idx[idx]]
        jwst_compact[jid] = {
            "ra": clean_num(j["ra"], 6),
            "dec": clean_num(j["dec"], 6),
            "z_phot": clean_num(j.get("z_phot"), 3),
            "z025": clean_num(j.get("z025"), 3),
            "z975": clean_num(j.get("z975"), 3),
            "risk": clean_num(j.get("z_phot_risk"), 3),
            "f_star": int(float(j.get("flag_star", 0))),
            "match_r": str(nearest_r["id"]),
            "sep": clean_num(j2r_dist[idx], 3),
        }

    # Initial 22 matched high-z sample
    sample_22 = [
        "5545", "2901", "3598", "4306", "932", "1977", "1600", "2512", "4039",
        "1262", "5665", "1899", "4260", "3720", "781", "4006", "327", "1801",
        "4335", "5625", "1184", "4763"
    ]

    out_data = {
        "cluster": "PG004",
        "sample_22": sample_22,
        "counts": {
            "jwst": len(jwst_list),
            "relics": len(relics_list),
            "sample_22": len(sample_22),
        },
        "relics": relics_compact,
        "jwst": jwst_compact,
    }

    out_file = Path("pg004_catalog.json")
    out_file.write_text(json.dumps(out_data, separators=(",", ":")), encoding="utf-8")
    print(f"✅ Generated {out_file} in {time.time()-t0:.2f}s ({out_file.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    main()
