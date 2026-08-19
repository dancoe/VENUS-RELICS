#!/usr/bin/env python3
"""Match the RELICS HST catalog to the JWST catalog in sky coordinates."""

import argparse
import csv
import math
import statistics
from pathlib import Path


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def projected_delta(hst_row, jwst_row, ra_shift_arcsec=0.0, dec_shift_arcsec=0.0):
    hst_ra = float(hst_row["ra"])
    hst_dec = float(hst_row["dec"]) + dec_shift_arcsec / 3600.0
    mean_dec = (hst_dec + float(jwst_row["dec"])) / 2.0
    delta_ra = (float(jwst_row["ra"]) - hst_ra) * math.cos(math.radians(mean_dec)) * 3600.0
    delta_ra -= ra_shift_arcsec
    delta_dec = (float(jwst_row["dec"]) - hst_dec) * 3600.0
    return delta_ra, delta_dec, math.hypot(delta_ra, delta_dec)


def corrected_coordinates(hst_row, ra_shift_arcsec, dec_shift_arcsec):
    dec = float(hst_row["dec"]) + dec_shift_arcsec / 3600.0
    ra = float(hst_row["ra"]) + ra_shift_arcsec / (3600.0 * math.cos(math.radians(dec)))
    return ra, dec


def make_match(hst_rows, jwst_rows, match_radius):
    initial_pairs = []
    for hst_row in hst_rows:
        nearest = min(
            ((projected_delta(hst_row, jwst_row), jwst_row) for jwst_row in jwst_rows),
            key=lambda item: item[0][2],
        )
        if nearest[0][2] < 1.0:
            initial_pairs.append(nearest[0])

    ra_shift = statistics.median(pair[0] for pair in initial_pairs)
    dec_shift = statistics.median(pair[1] for pair in initial_pairs)

    candidates = []
    for hst_index, hst_row in enumerate(hst_rows):
        for jwst_index, jwst_row in enumerate(jwst_rows):
            residual = projected_delta(hst_row, jwst_row, ra_shift, dec_shift)
            if residual[2] <= match_radius:
                candidates.append((residual[2], hst_index, jwst_index, residual))
    candidates.sort(key=lambda item: item[0])

    assigned_hst = set()
    assigned_jwst = set()
    matches = {}
    for _, hst_index, jwst_index, residual in candidates:
        if hst_index in assigned_hst or jwst_index in assigned_jwst:
            continue
        assigned_hst.add(hst_index)
        assigned_jwst.add(jwst_index)
        matches[hst_index] = (jwst_index, residual)

    metadata_fields = [
        "match_status", "jwst_match_id", "nearest_jwst_id",
        "raw_separation_arcsec", "corrected_separation_arcsec",
        "raw_delta_ra_arcsec", "raw_delta_dec_arcsec",
        "corrected_delta_ra_arcsec", "corrected_delta_dec_arcsec",
        "hst_ra_corrected_deg", "hst_dec_corrected_deg",
        "estimated_offset_ra_arcsec", "estimated_offset_dec_arcsec",
        "match_radius_arcsec",
    ]
    fieldnames = metadata_fields
    fieldnames += [f"hst_{field}" for field in hst_rows[0]]
    fieldnames += [f"jwst_{field}" for field in jwst_rows[0]]

    output_rows = []
    for hst_index, hst_row in enumerate(hst_rows):
        match = matches.get(hst_index)
        if match is not None:
            jwst_index, corrected = match
            jwst_row = jwst_rows[jwst_index]
            raw = projected_delta(hst_row, jwst_row)
            status = "matched"
            match_id = jwst_row["id"]
            nearest_id = match_id
            corrected_distance = corrected[2]
            corrected_delta_ra, corrected_delta_dec = corrected[:2]
        else:
            jwst_row = None
            raw = (None, None, None)
            nearest_candidates = sorted(
                ((projected_delta(hst_row, candidate, ra_shift, dec_shift), candidate)
                 for candidate in jwst_rows),
                key=lambda item: item[0][2],
            )
            corrected, nearest_row = nearest_candidates[0]
            status = "unmatched"
            match_id = ""
            nearest_id = nearest_row["id"]
            corrected_distance = corrected[2]
            corrected_delta_ra, corrected_delta_dec = corrected[:2]

        corrected_ra, corrected_dec = corrected_coordinates(hst_row, ra_shift, dec_shift)
        joined = {
            "match_status": status,
            "jwst_match_id": match_id,
            "nearest_jwst_id": nearest_id,
            "raw_separation_arcsec": "" if raw[2] is None else f"{raw[2]:.6f}",
            "corrected_separation_arcsec": f"{corrected_distance:.6f}",
            "raw_delta_ra_arcsec": "" if raw[0] is None else f"{raw[0]:.6f}",
            "raw_delta_dec_arcsec": "" if raw[1] is None else f"{raw[1]:.6f}",
            "corrected_delta_ra_arcsec": f"{corrected_delta_ra:.6f}",
            "corrected_delta_dec_arcsec": f"{corrected_delta_dec:.6f}",
            "hst_ra_corrected_deg": f"{corrected_ra:.10f}",
            "hst_dec_corrected_deg": f"{corrected_dec:.10f}",
            "estimated_offset_ra_arcsec": f"{ra_shift:.6f}",
            "estimated_offset_dec_arcsec": f"{dec_shift:.6f}",
            "match_radius_arcsec": f"{match_radius:.2f}",
        }
        joined.update({f"hst_{field}": value for field, value in hst_row.items()})
        joined.update({f"jwst_{field}": value for field, value in (jwst_row or {}).items()})
        output_rows.append(joined)

    return fieldnames, output_rows, ra_shift, dec_shift


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--hst", type=Path,
        default=Path("PG004-RELICS z ~ 6 –\u00a010 - z~6-10.csv"),
        help="RELICS HST catalog CSV",
    )
    parser.add_argument(
        "--jwst", type=Path, default=Path("pg004_aphot_cut_wzphots.csv"),
        help="JWST catalog CSV",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("relics_jwst_coordinate_match.csv"),
        help="Output crossmatch CSV",
    )
    parser.add_argument(
        "--radius", type=float, default=0.2,
        help="Corrected one-to-one match radius in arcsec (default: 0.2)",
    )
    args = parser.parse_args()

    hst_rows = read_csv(args.hst)
    jwst_rows = read_csv(args.jwst)
    fieldnames, output_rows, ra_shift, dec_shift = make_match(
        hst_rows, jwst_rows, args.radius
    )

    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    matched = sum(row["match_status"] == "matched" for row in output_rows)
    print(f"Wrote {args.output} with {len(output_rows)} rows")
    print(f"Matched: {matched}; unmatched: {len(output_rows) - matched}")
    print(f"Estimated offset: dRA={ra_shift:.6f} arcsec, dDec={dec_shift:.6f} arcsec")


if __name__ == "__main__":
    main()