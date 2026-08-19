# RELICS × VENUS Crossmatch & High-z Analysis (Field: PG004 / PLCKG004-19)

This repository contains catalogs, analysis scripts, photometric-redshift comparisons, and an interactive HTML evidence browser matching **HST RELICS** and **JWST VENUS** observations of cluster field **PLCKG004-19** (PG004).

---

## 📑 Overview of Documents & Reports

* **[RELICS_VENUS.md](RELICS_VENUS.md)**:
  Detailed scientific report on matching the original 28 RELICS HST high-$z$ candidates ($z \sim 6\text{--}10$) against the 11,699-source JWST catalog. 22 sources match within a 0.20″ corrected radius after applying the global astrometric shift ($\Delta\text{RA} = +0.536463″$, $\Delta\text{Dec} = -0.001390″$).
* **[VENUS_RELICS.md](VENUS_RELICS.md)**:
  Reverse selection report: selects 532 confident JWST high-$z$ candidates ($z_\mathrm{phot} \ge 6.0$, $z_{025} \ge 4.5$, $z_{500} \ge 6.0$, $\mathrm{risk} < 0.2$, $N_\mathrm{usefilt} \ge 10$) and matches them against the full 2,738-source RELICS HST catalog.
* **[RELICS_VENUS.html](RELICS_VENUS.html)**:
  Interactive side-by-side visual browser displaying matched targets with:
  1. HST ACS + IR color stamps
  2. RELICS BPZ SED fits
  3. RELICS BPZ $P(z)$ probability distributions
  4. JWST VENUS EAZY SED fits & $P(z)$ posteriors

---

## 🚀 How to Share, Query, & Generate Webpages

The script [`make_relics_venus_html.py`](make_relics_venus_html.py) is scriptable and supports CLI filtering, on-the-fly crossmatching, automatic EAZY plot downloading, and a local interactive web server.

### 1. Generate Custom Webpage for Specific IDs (CLI)

You can pass one or more **RELICS HST IDs** or **JWST VENUS IDs** (space-separated or comma-separated):

```bash
# Generate page for specific VENUS IDs
.venv/bin/python make_relics_venus_html.py --venus-ids 5545 1600 4039 --output custom_venus.html

# Generate page for specific RELICS IDs
.venv/bin/python make_relics_venus_html.py --relics-ids 222 1983 2057 --output custom_relics.html

# Mix both VENUS and RELICS IDs
.venv/bin/python make_relics_venus_html.py --venus-ids 5545 --relics-ids 1983 --output mixed.html
```
*Missing EAZY plot assets are automatically fetched and authenticated against VENUS Hub.*

### 2. Run Interactive Local Web Server / Search UI

```bash
.venv/bin/python make_relics_venus_html.py --serve --port 8000
```
* Opens `http://localhost:8000/RELICS_VENUS.html` in your browser.
* Provides a **real-time instant search bar** to filter targets by ID.
* Provides a dynamic backend search endpoint:
  ```
  http://localhost:8000/api/search?venus_id=5545,1600&relics_id=222
  ```

### 3. Share as a Static Site (e.g. GitHub Pages / Lab Server)
* Push the repository or copy `RELICS_VENUS.html` along with the `venus_eazy/` directory to any static web host or GitHub Pages repository.
* Since all RELICS assets are public and the VENUS EAZY panels are cached locally, anyone can browse without needing credentials.

---

## 📊 Catalogs & Datasets

| File | Description |
| :--- | :--- |
| `PG004-RELICS z ~ 6 – 10 - z~6-10.csv` | Original RELICS HST $z \sim 6\text{--}10$ candidate sample (28 objects). |
| `pg004_aphot_cut_wzphots.csv` | Full JWST aperture photometry + photo-$z$ catalog (11,699 objects). |
| `plckg004-19.cat` | Full RELICS HST detection catalog (2,738 objects). |
| `relics_jwst_coordinate_match.csv` | Crossmatch results for the 28 RELICS HST high-$z$ candidates vs. JWST. |
| `venus_highz_relics_match.csv` | Crossmatch results for the 532 JWST high-$z$ candidates vs. full HST catalog. |

---

## 🛠️ Analysis Workflows

```bash
# 1. Match RELICS High-z to JWST
.venv/bin/python match_relics_jwst.py --radius 0.20

# 2. Plot Redshift Comparison (z_HST vs. z_JWST)
.venv/bin/python plot_jwst_vs_photoz.py

# 3. Match JWST High-z Candidates to Full HST Catalog
.venv/bin/python match_venus_relics.py --min-z-phot 6 --min-z025 4.5 --match-radius 0.2
```
