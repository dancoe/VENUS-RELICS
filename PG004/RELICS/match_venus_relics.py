#!/usr/bin/env python3
"""Select JWST VENUS high-z candidates and match them to full RELICS."""

import argparse
import csv
import math
from pathlib import Path


DEFAULT_RA_OFFSET_ARCSEC = 0.536463
DEFAULT_DEC_OFFSET_ARCSEC = -0.001390


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def read_relics_catalog(path):
    lines = path.read_text().splitlines()
    header_line = next(line for line in lines if line.startswith("##  id"))
    fields = header_line[2:].split()
    rows = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        values = line.split()
        if len(values) == len(fields):
            rows.append(dict(zip(fields, values)))
    return fields, rows


def number(row, field):
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def is_high_z_candidate(row, args):
    required = ("z_phot", "z025", "z500", "z_phot_risk", "nusefilt", "flag_star", "flag_bcg")
    values = {field: number(row, field) for field in required}
    if any(value is None for value in values.values()):
        return False
    return (
        values["z_phot"] >= args.min_z_phot
        and values["z025"] >= args.min_z025
        and values["z500"] >= args.min_z500
        and 0 <= values["z_phot_risk"] < args.max_risk
        and values["nusefilt"] >= args.min_nusefilt
        and values["flag_star"] == 0
        and values["flag_bcg"] == 0
    )


def projected_delta(jwst_row, relics_row, ra_offset_arcsec, dec_offset_arcsec):
    jwst_ra = float(jwst_row["ra"])
    jwst_dec = float(jwst_row["dec"])
    relics_ra = float(relics_row["RA"])
    relics_dec = float(relics_row["Dec"])
    mean_dec = (jwst_dec + relics_dec) / 2.0
    delta_ra = (jwst_ra - relics_ra) * math.cos(math.radians(mean_dec)) * 3600.0
    delta_dec = (jwst_dec - relics_dec) * 3600.0
    raw_distance = math.hypot(delta_ra, delta_dec)
    corrected_delta_ra = delta_ra - ra_offset_arcsec
    corrected_delta_dec = delta_dec - dec_offset_arcsec
    corrected_distance = math.hypot(corrected_delta_ra, corrected_delta_dec)
    return (
        delta_ra,
        delta_dec,
        raw_distance,
        corrected_delta_ra,
        corrected_delta_dec,
        corrected_distance,
    )


def match_candidates(candidates, relics_rows, args):
    pairs = []
    for jwst_index, jwst_row in enumerate(candidates):
        for relics_index, relics_row in enumerate(relics_rows):
            residual = projected_delta(
                jwst_row,
                relics_row,
                args.ra_offset_arcsec,
                args.dec_offset_arcsec,
            )
            if residual[5] <= args.match_radius:
                pairs.append((residual[5], jwst_index, relics_index, residual))
    pairs.sort(key=lambda item: item[0])

    assigned_jwst = set()
    assigned_relics = set()
    matches = {}
    for _, jwst_index, relics_index, residual in pairs:
        if jwst_index in assigned_jwst or relics_index in assigned_relics:
            continue
        assigned_jwst.add(jwst_index)
        assigned_relics.add(relics_index)
        matches[jwst_index] = (relics_index, residual)
    return matches


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--jwst", type=Path, default=Path("pg004_aphot_cut_wzphots.csv"),
        help="JWST VENUS catalog CSV",
    )
    parser.add_argument(
        "--relics", type=Path, default=Path("plckg004-19.cat"),
        help="Full RELICS catalog downloaded from relics.stsci.edu",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("venus_highz_relics_match.csv"),
        help="Output candidate crossmatch CSV",
    )
    parser.add_argument("--min-z-phot", type=float, default=6.0)
    parser.add_argument("--min-z025", type=float, default=4.5)
    parser.add_argument("--min-z500", type=float, default=6.0)
    parser.add_argument("--max-risk", type=float, default=0.2)
    parser.add_argument("--min-nusefilt", type=float, default=10)
    parser.add_argument("--match-radius", type=float, default=0.2)
    parser.add_argument("--ra-offset-arcsec", type=float, default=DEFAULT_RA_OFFSET_ARCSEC)
    parser.add_argument("--dec-offset-arcsec", type=float, default=DEFAULT_DEC_OFFSET_ARCSEC)
    args = parser.parse_args()

    jwst_rows = read_csv(args.jwst)
    relics_fields, relics_rows = read_relics_catalog(args.relics)
    candidates = [row for row in jwst_rows if is_high_z_candidate(row, args)]
    matches = match_candidates(candidates, relics_rows, args)

    metadata_fields = [
        "high_z_candidate", "match_status", "relics_match_id", "nearest_relics_id",
        "raw_separation_arcsec", "corrected_separation_arcsec",
        "raw_delta_ra_arcsec", "raw_delta_dec_arcsec",
        "corrected_delta_ra_arcsec", "corrected_delta_dec_arcsec",
        "ra_offset_arcsec", "dec_offset_arcsec", "match_radius_arcsec",
        "selection_min_z_phot", "selection_min_z025", "selection_min_z500",
        "selection_max_z_phot_risk", "selection_min_nusefilt",
    ]
    fieldnames = metadata_fields
    fieldnames += [f"jwst_{field}" for field in jwst_rows[0]]
    fieldnames += [f"relics_{field}" for field in relics_fields]

    output_rows = []
    for jwst_index, jwst_row in enumerate(candidates):
        match = matches.get(jwst_index)
        if match is not None:
            relics_index, residual = match
            relics_row = relics_rows[relics_index]
            nearest_id = relics_row["id"]
            status = "matched"
        else:
            nearest = min(
                (
                    (projected_delta(
                        jwst_row,
                        relics_row,
                        args.ra_offset_arcsec,
                        args.dec_offset_arcsec,
                    ), relics_index, relics_row)
                    for relics_index, relics_row in enumerate(relics_rows)
                ),
                key=lambda item: item[0][5],
            )
            residual, relics_index, relics_row = nearest
            nearest_id = relics_row["id"]
            status = "unmatched"

        joined = {
            "high_z_candidate": "1",
            "match_status": status,
            "relics_match_id": relics_row["id"] if match is not None else "",
            "nearest_relics_id": nearest_id,
            "raw_separation_arcsec": f"{residual[2]:.6f}",
            "corrected_separation_arcsec": f"{residual[5]:.6f}",
            "raw_delta_ra_arcsec": f"{residual[0]:.6f}",
            "raw_delta_dec_arcsec": f"{residual[1]:.6f}",
            "corrected_delta_ra_arcsec": f"{residual[3]:.6f}",
            "corrected_delta_dec_arcsec": f"{residual[4]:.6f}",
            "ra_offset_arcsec": f"{args.ra_offset_arcsec:.6f}",
            "dec_offset_arcsec": f"{args.dec_offset_arcsec:.6f}",
            "match_radius_arcsec": f"{args.match_radius:.2f}",
            "selection_min_z_phot": f"{args.min_z_phot:.2f}",
            "selection_min_z025": f"{args.min_z025:.2f}",
            "selection_min_z500": f"{args.min_z500:.2f}",
            "selection_max_z_phot_risk": f"{args.max_risk:.2f}",
            "selection_min_nusefilt": f"{args.min_nusefilt:.0f}",
        }
        joined.update({f"jwst_{field}": value for field, value in jwst_row.items()})
        joined.update({f"relics_{field}": value for field, value in relics_row.items()})
        output_rows.append(joined)

    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    matched = sum(row["match_status"] == "matched" for row in output_rows)
    print(f"JWST high-z candidates: {len(candidates)}")
    print(f"Matched to full RELICS: {matched}; unmatched: {len(candidates) - matched}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()