#!/usr/bin/env python3
"""Plot JWST photometric redshift against the matched RELICS photo-z."""

import argparse
import csv
import math
from pathlib import Path


def finite_float(row, field):
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def error_pair(row, central_field, low_field, high_field):
    central = finite_float(row, central_field)
    low = finite_float(row, low_field)
    high = finite_float(row, high_field)
    if central is None or low is None or high is None or low > central or high < central:
        return None
    return central, central - low, high - central


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", type=Path, default=Path("relics_jwst_coordinate_match.csv"),
        help="Coordinate-match CSV",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("jwst_vs_relics_photoz.png"),
        help="Output PNG",
    )
    parser.add_argument(
        "--x-column", default="hst_z",
        help="HST photo-z central-value column (default: hst_z)",
    )
    parser.add_argument(
        "--x-low", default="hst_zbmin",
        help="HST lower redshift bound (default: hst_zbmin)",
    )
    parser.add_argument(
        "--x-high", default="hst_zbmax",
        help="HST upper redshift bound (default: hst_zbmax)",
    )
    parser.add_argument(
        "--y-column", default="jwst_z_phot",
        help="JWST photo-z central-value column (default: jwst_z_phot)",
    )
    parser.add_argument(
        "--y-low", default="jwst_z025",
        help="JWST lower redshift bound (default: jwst_z025)",
    )
    parser.add_argument(
        "--y-high", default="jwst_z975",
        help="JWST upper redshift bound (default: jwst_z975)",
    )
    parser.add_argument(
        "--title", default="JWST vs. RELICS photometric redshift",
        help="Plot title",
    )
    args = parser.parse_args()

    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise SystemExit(
            "This script requires matplotlib. Install it with: python3 -m pip install matplotlib"
        ) from error

    with args.input.open(newline="") as stream:
        rows = list(csv.DictReader(stream))

    points = []
    for row in rows:
        if row.get("match_status") != "matched":
            continue
        x_error = error_pair(row, args.x_column, args.x_low, args.x_high)
        y_error = error_pair(row, args.y_column, args.y_low, args.y_high)
        if x_error is None or y_error is None:
            continue
        points.append((row, x_error, y_error))

    if not points:
        raise SystemExit("No matched rows have valid central redshifts and error bounds.")

    x_values = [point[1][0] for point in points]
    y_values = [point[2][0] for point in points]
    x_errors = [[point[1][1] for point in points], [point[1][2] for point in points]]
    y_errors = [[point[2][1] for point in points], [point[2][2] for point in points]]
    lower = min(x_values + y_values)
    upper = max(x_values + y_values)
    padding = max(0.25, (upper - lower) * 0.08)

    figure, axis = plt.subplots(figsize=(7.5, 7.0), constrained_layout=True)
    axis.errorbar(
        x_values, y_values, xerr=x_errors, yerr=y_errors,
        fmt="o", markersize=5, color="#176b87", ecolor="#6f8f9b",
        elinewidth=1, capsize=2, alpha=0.9,
    )
    axis.plot(
        [lower - padding, upper + padding], [lower - padding, upper + padding],
        linestyle="--", color="#444444", linewidth=1, label="1:1",
    )
    for row, x_error, y_error in points:
        axis.annotate(
            row["hst_ID"], (x_error[0], y_error[0]),
            xytext=(4, 4), textcoords="offset points", fontsize=7, color="#333333",
        )

    axis.set_xlim(lower - padding, upper + padding)
    axis.set_ylim(lower - padding, upper + padding)
    axis.set_xlabel("RELICS HST photo-z")
    axis.set_ylabel("JWST photo-z")
    axis.set_title(args.title)
    axis.grid(True, color="#d9e1e5", linewidth=0.7)
    axis.legend(frameon=False)
    figure.savefig(args.output, dpi=200)
    plt.close(figure)
    print(f"Wrote {args.output} with {len(points)} plotted matches")


if __name__ == "__main__":
    main()