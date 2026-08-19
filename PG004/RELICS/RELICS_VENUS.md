# RELICS-VENUS Catalog Matching Report

**Date:** 2026-08-05  
**Field:** PLCKG004-19 / PG004  
**Purpose:** Match the RELICS HST catalog to the JWST catalog in sky position and compare their photometric redshifts.

## Input Catalogs

The analysis uses the following files:

| Catalog | File | Rows | Coordinate columns |
| --- | --- | ---: | --- |
| RELICS HST | `PG004-RELICS z ~ 6 –\u00a010 - z~6-10.csv` | 28 | `ra`, `dec` |
| JWST | `pg004_aphot_cut_wzphots.csv` | 11,699 | `ra`, `dec` |

The coordinates are interpreted as decimal degrees. The RELICS source identifier is `ID`; the JWST source identifier is `id`.

## Coordinate Matching

### Astrometric offset

For each RELICS source, the nearest JWST source was first identified using the sky separation in the tangent-plane approximation:

$$
\Delta x = (\mathrm{RA}_{JWST} - \mathrm{RA}_{HST})\cos(\bar{\delta})\times 3600,
$$

$$
\Delta y = (\mathrm{Dec}_{JWST} - \mathrm{Dec}_{HST})\times 3600,
$$

where the separations are in arcseconds and $\bar{\delta}$ is the mean declination.

The initial close neighbors show a systematic offset of:

```text
JWST - HST projected RA:  +0.536463 arcsec
JWST - HST Dec:            -0.001390 arcsec
```

The offsets are the medians of the initial nearest-neighbor offsets for sources within 1 arcsecond.

To transform JWST coordinates onto the HST coordinate frame, subtract `0.536463` arcsec from the JWST projected RA and add `0.001390` arcsec to the JWST Dec. Equivalently, add the opposite offset to the HST coordinates. The RA offset corresponds to approximately `0.00017875` degrees at this declination, but the cosine declination factor should be retained when converting between projected RA and catalog RA.

### Matching rule

After applying the offset, candidate pairs were retained when their residual separation was at most:

```text
0.20 arcsec
```

Candidates were sorted by residual separation and assigned greedily, with each HST source and each JWST source allowed to appear in at most one match. The resulting match is therefore one-to-one within the adopted radius.

## Match Results

| Result | Count |
| --- | ---: |
| RELICS HST sources | 28 |
| Matched HST sources | 22 |
| Unmatched HST sources | 6 |
| Unique JWST IDs among matches | 22 |

The corrected separations for the 22 matches are:

| Statistic | Separation |
| --- | ---: |
| Minimum | `0.003831 arcsec` |
| Median | `0.025024 arcsec` |
| Mean | `0.031757 arcsec` |
| Maximum | `0.086203 arcsec` |

For comparison, the raw separations before applying the astrometric offset had a median of `0.544293 arcsec` and a maximum of `0.590518 arcsec` for the matched sources.

The unmatched RELICS source IDs are:

```text
2691, 1932, 2698, 1508, 1441, 2704
```

Their nearest offset-corrected JWST candidates are still approximately 4.9--11.2 arcsec away, so they were not assigned counterparts under the 0.20 arcsec criterion.

## Output Crossmatch Catalog

The full crossmatch is saved as:

`relics_jwst_coordinate_match.csv`

The output retains every RELICS row. HST columns are prefixed with `hst_`, and JWST columns are prefixed with `jwst_`. Important match metadata include:

| Column | Meaning |
| --- | --- |
| `match_status` | `matched` or `unmatched` |
| `jwst_match_id` | Assigned JWST source ID; blank for unmatched sources |
| `nearest_jwst_id` | Nearest JWST candidate after offset correction |
| `raw_separation_arcsec` | Separation before offset correction |
| `corrected_separation_arcsec` | Residual separation after offset correction |
| `corrected_delta_ra_arcsec` | Offset-corrected projected RA residual |
| `corrected_delta_dec_arcsec` | Offset-corrected Dec residual |
| `estimated_offset_ra_arcsec` | Applied projected RA offset, `0.536463` arcsec |
| `estimated_offset_dec_arcsec` | Applied Dec offset, `-0.001390` arcsec |
| `match_radius_arcsec` | Adopted residual matching radius, `0.20` arcsec |

## Photometric-Redshift Comparison

The comparison plot is saved as:

`jwst_vs_relics_photoz.png`

The plotting script uses only matched rows with valid central values and valid bounds:

| Quantity | Central value | Lower bound | Upper bound |
| --- | --- | --- | --- |
| RELICS HST photo-z | `hst_z` | `hst_zbmin` | `hst_zbmax` |
| JWST photo-z | `jwst_z_phot` | `jwst_z025` | `jwst_z975` |

The error bars are asymmetric. For a central value $z$ and bounds $z_{low}$ and $z_{high}$, the plotted errors are:

$$
\sigma_{-} = z - z_{low}, \qquad \sigma_{+} = z_{high} - z.
$$

Of the 22 coordinate matches, 16 have valid JWST photo-z values and quantile bounds and are included in the plot. Six JWST rows contain sentinel values such as `-1` or zero quantiles and are excluded from the redshift plot; this exclusion does not remove them from the coordinate-match catalog.

The plot includes a dashed 1:1 line and labels each point with its RELICS HST source ID.

## Reproduction

The coordinate matching workflow is saved in:

`match_relics_jwst.py`

Run it from this directory with:

```bash
.venv/bin/python match_relics_jwst.py
```

The default inputs and output are the files listed above. A different matching radius can be supplied with, for example:

```bash
.venv/bin/python match_relics_jwst.py --radius 0.20
```

The redshift plot is generated with:

```bash
.venv/bin/python plot_jwst_vs_photoz.py
```

The plotting environment uses `matplotlib`. The script also supports alternate central-value and uncertainty columns through `--x-column`, `--x-low`, `--x-high`, `--y-column`, `--y-low`, and `--y-high`.

## Caveats

1. The matching uses a single global astrometric shift estimated from the initial close pairs. It does not model spatially varying distortion, catalog-specific uncertainties, or proper motion.
2. The one-to-one assignments are nearest-separation assignments after the offset correction. In crowded regions, source morphology, fluxes, or an assignment model could provide additional validation.
3. The RELICS `zbmin` and `zbmax` fields can span broad or multimodal photometric-redshift solutions. They are plotted as bounds, not necessarily as Gaussian $1\sigma$ uncertainties.
4. The JWST `z025` and `z975` fields are used as lower and upper quantiles for the plotted error bars. Rows with invalid sentinel values are excluded from the plot.
