# JWST VENUS High-z Candidates Matched to RELICS HST

**Date:** 2026-08-05  
**Field:** PLCKG004-19 / PG004  
**Purpose:** Select confident high-redshift candidates from the JWST VENUS catalog, match them to the complete RELICS HST catalog, and evaluate the redshifts assigned by RELICS.

## Data

### JWST VENUS catalog

The JWST catalog is:

`pg004_aphot_cut_wzphots.csv`

It contains 11,699 sources with decimal-degree `ra` and `dec` coordinates. The high-z selection uses the JWST photometric-redshift and quality fields `z_phot`, `z025`, `z500`, `z_phot_risk`, `nusefilt`, `flag_star`, and `flag_bcg`.

### Full RELICS HST catalog

The complete RELICS IR-detection catalog was downloaded from:

<https://relics.stsci.edu/HST/plckg004-19/final_processing/catalogs/IR_detection/plckg004-19.cat>

The downloaded local copy is:

`plckg004-19.cat`

It contains 2,738 HST sources and 73 whitespace-delimited columns. The HST coordinates are `RA` and `Dec`. The RELICS BPZ fields used for comparison are:

| Field | Meaning |
| --- | --- |
| `zb` | BPZ most-likely redshift |
| `zbmin`, `zbmax` | RELICS 95% confidence range |
| `odds` | BPZ ODDS statistic |
| `chisq`, `chisq2` | BPZ fit statistics |
| `zml` | Maximum-likelihood redshift |
| `stel` | SExtractor stellarity, where values near 1 are star-like |

The RELICS catalog documentation notes that the photo-z estimates are intended for galaxies and that high SExtractor stellarity can identify stars.

## JWST High-z Selection

The primary sample is deliberately conservative and is defined by all of the following conditions:

```text
z_phot >= 6.0
z025 >= 4.5
z500 >= 6.0
z_phot_risk < 0.2
nusefilt >= 10
flag_star == 0
flag_bcg == 0
```

The interpretation is:

- `z_phot >= 6` selects a high-redshift JWST solution.
- `z025 >= 4.5` requires the lower 2.5% posterior quantile to remain above the usual high-z threshold.
- `z500 >= 6` requires the posterior median to remain in the high-z regime.
- `z_phot_risk < 0.2` applies a low-risk photo-z cut.
- `nusefilt >= 10` requires broad JWST filter coverage.
- JWST sources flagged as stars or BCGs are excluded.

This selection yields **532 JWST high-z candidates**. The thresholds are recorded in every row of the output catalog so that the sample can be reproduced or modified.

## Coordinate Offset and Matching

The same global astrometric offset measured from the previous RELICS-to-JWST comparison was applied:

```text
JWST - HST projected RA:  +0.536463 arcsec
JWST - HST Dec:            -0.001390 arcsec
```

For a JWST source and an HST source, the raw tangent-plane offsets are:

$$
\Delta x = (\mathrm{RA}_{JWST} - \mathrm{RA}_{HST})\cos(\bar{\delta})\times 3600,
$$

$$
\Delta y = (\mathrm{Dec}_{JWST} - \mathrm{Dec}_{HST})\times 3600.
$$

The corrected residuals are:

$$
\Delta x_{corr} = \Delta x - 0.536463,
$$

$$
\Delta y_{corr} = \Delta y - (-0.001390).
$$

JWST candidates were matched to the full HST catalog using a one-to-one nearest-neighbor assignment with a corrected separation limit of `0.20 arcsec`.

## Crossmatch Results

| Result | Count |
| --- | ---: |
| Selected JWST high-z candidates | 532 |
| Matched to a unique RELICS HST source | 182 |
| Without a RELICS match within `0.20 arcsec` | 350 |
| Unique HST IDs among matched candidates | 182 |

For the 182 matched candidates, the coordinate separations are:

| Statistic | Raw separation | Corrected separation |
| --- | ---: | ---: |
| Minimum | `0.449387 arcsec` | `0.003831 arcsec` |
| Median | `0.544507 arcsec` | `0.054785 arcsec` |
| Mean | `0.545030 arcsec` | `0.058950 arcsec` |
| Maximum | `0.662117 arcsec` | `0.161702 arcsec` |

The offset therefore brings the selected JWST sources into close positional agreement with the HST catalog for the matched subset.

## What RELICS Assigned

The following statistics apply only to the 182 JWST candidates with an HST counterpart. They intentionally overlap because they describe different aspects of the RELICS BPZ solution.

| RELICS criterion | Matched candidates |
| --- | ---: |
| `zb >= 6` | 8 |
| `zbmin >= 4.5` | 79 |
| `zbmax >= 6` | 20 |
| Both `zb >= 6` and `zbmin >= 4.5` | 4 |
| HST `stel >= 0.8` (star-like) | 143 |
| HST `zbmax < 4.5` | 52 |

The strictest direct agreement criterion is `zb >= 6` with `zbmin >= 4.5`. Only four sources satisfy it:

| JWST ID | JWST `z_phot` | RELICS ID | RELICS `zb` | RELICS `zbmin` | RELICS `zbmax` | RELICS `odds` | HST `stel` |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1600 | 6.578 | 2057 | 6.054 | 5.485 | 6.422 | 0.767 | 0.950 |
| 1801 | 6.797 | 1983 | 6.403 | 5.774 | 7.026 | 0.707 | 0.780 |
| 3756 | 6.427 | 1356 | 6.079 | 5.966 | 6.141 | 1.000 | 0.980 |
| 4039 | 6.800 | 936 | 6.333 | 5.890 | 6.812 | 0.812 | 0.960 |

Three of these four strict HST high-z agreements are also star-like by the simple `stel >= 0.8` diagnostic. The one strict high-z and non-star-like match in this sample is JWST ID `1801`, matched to RELICS ID `1983`.

## Interpretation

For this selection, RELICS does **not** independently confirm most of the JWST high-z candidates as ordinary high-z galaxies. Among the 182 sources with HST counterparts:

- 8 have a RELICS most-likely BPZ redshift of at least 6.
- 4 have both a most-likely RELICS redshift of at least 6 and a 95% lower bound above 4.5.
- 143 are star-like in the HST detection catalog by `stel >= 0.8`.
- 52 have RELICS 95% upper limits below 4.5 and are therefore strongly inconsistent with a high-z solution under the RELICS BPZ fit.

The large number of star-like HST counterparts is important. The JWST selection excluded the JWST catalog's `flag_star` sources, but that does not guarantee that a source will not be star-like in the independent HST morphology measurement. The high JWST photo-z solutions may also represent color-redshift degeneracies, unresolved or blended sources, or sources whose HST photometry is not sufficiently constraining.

The 350 JWST candidates without a match within `0.20 arcsec` should not automatically be treated as HST non-detections: they may lie outside the effective HST detection footprint, fall below the HST detection threshold, be affected by segmentation differences, or have a residual astrometric/morphological mismatch. Their nearest HST diagnostics are retained in the output for follow-up.

## Output Catalog

The candidate crossmatch is saved as:

`venus_highz_relics_match.csv`

The output contains one row per selected JWST candidate. JWST columns are prefixed with `jwst_`; RELICS columns are prefixed with `relics_`. Important metadata columns are:

| Column | Meaning |
| --- | --- |
| `match_status` | `matched` or `unmatched` |
| `relics_match_id` | Assigned RELICS HST ID; blank if unmatched |
| `nearest_relics_id` | Nearest HST candidate after offset correction |
| `raw_separation_arcsec` | Separation before applying the offset |
| `corrected_separation_arcsec` | Residual separation after applying the offset |
| `relics_zb`, `relics_zbmin`, `relics_zbmax` | RELICS BPZ redshift and 95% range |
| `relics_odds` | RELICS BPZ ODDS statistic |
| `relics_stel` | HST SExtractor stellarity |
| `ra_offset_arcsec`, `dec_offset_arcsec` | Applied astrometric offset |
| `selection_*` | High-z selection thresholds used for the row |

## Reproduction

The dedicated workflow is saved in:

`match_venus_relics.py`

Run it from this directory with:

```bash
.venv/bin/python match_venus_relics.py
```

The default command reads `pg004_aphot_cut_wzphots.csv` and `plckg004-19.cat`, then writes `venus_highz_relics_match.csv`.

The selection can be changed from the command line. For example:

```bash
.venv/bin/python match_venus_relics.py \
  --min-z-phot 6 \
  --min-z025 4.5 \
  --min-z500 6 \
  --max-risk 0.2 \
  --min-nusefilt 10 \
  --match-radius 0.2
```

## Caveats

1. The HST and JWST catalogs use different photometric models, filters, depths, segmentation, and redshift estimators. Agreement or disagreement in photo-z is not by itself a definitive physical classification.
2. The global coordinate offset was measured previously and reused here. This analysis does not fit a new spatially varying astrometric solution.
3. The matching radius is a residual coordinate criterion, not a probabilistic association probability.
4. RELICS explicitly cautions that its photo-z estimates are intended for galaxies. Star-like sources should be treated separately from normal galaxy candidates.
5. `zbmin` and `zbmax` are RELICS BPZ 95% confidence bounds and should not be interpreted as symmetric Gaussian errors.
6. The high JWST redshift values above approximately 10 are retained by the stated selection if they satisfy the posterior and quality cuts. They are not automatically confirmed high-redshift galaxies; they require inspection of the photometry, morphology, and full posterior.
