# AGENTS.md — Guidelines & Workflow Instructions for VENUS-RELICS

This document provides instructions for AI agents working in this repository (`/Users/dcoe/VENUS/`).

---

## 🔑 Git & Authentication

* **GitHub Repository:** `https://github.com/dancoe/VENUS-RELICS.git`
* **Git Credentials:** GitHub credentials (PAT) are stored in the macOS Keychain (`osxkeychain`) under user `dancoe`.
* **Git Push Capability:** You **can and should** commit and push directly to GitHub (`git push`) when publishing updates to the live site.
* **Live Site:** `https://dancoe.github.io/VENUS-RELICS/`

---

## 🏛️ Repository Architecture

The repository is structured to support multi-cluster high-$z$ crossmatching:

```text
/Users/dcoe/VENUS/
├── index.html                      # Root multi-cluster portal landing page
├── README.md                       # High-level repository documentation
├── AGENTS.md                       # Agent instructions (this file)
└── <CLUSTER>/                      # e.g., PG004
    └── RELICS/
        ├── index.html              # Copy of RELICS_VENUS.html for direct cluster root routing
        ├── RELICS_VENUS.html       # Full interactive evidence browser
        ├── make_relics_venus_html.py # Browser generator & local web server
        ├── generate_catalog_json.py  # Builds client-side compact crossmatch DB
        ├── <cluster>_catalog.json  # Compact pre-computed DB (11.7k JWST + 2.7k RELICS)
        ├── match_relics_jwst.py    # Crossmatch script (RELICS -> JWST)
        ├── match_venus_relics.py   # Crossmatch script (JWST high-z -> RELICS)
        ├── plot_jwst_vs_photoz.py  # Photo-z comparison plotter
        ├── venus_eazy/             # Full-height, authenticated EAZY SED & P(z) plots
        ├── *.csv / *.cat           # Catalogs & crossmatch data tables
        └── *.md                    # Scientific reports & documentation
```

---

## 🚀 Common Workflows

### 1. Rebuilding the HTML & Updating the Client Database
When modifying catalog data, offsets, or UI layout for a cluster:
```bash
cd /Users/dcoe/VENUS/PG004/RELICS
.venv/bin/python generate_catalog_json.py   # Rebuilds pg004_catalog.json
.venv/bin/python make_relics_venus_html.py    # Rebuilds RELICS_VENUS.html
cp RELICS_VENUS.html index.html              # Keep index.html synchronized
```

### 2. Downloading / Caching Authenticated VENUS EAZY Plots
* `venushub.astro.utoronto.ca` requires authentication (`POST /login` with Name: `Dan Coe`, Password: `l3nsing!`).
* `make_relics_venus_html.py` includes the automated `ensure_eazy_plot(jwst_id)` function which logs in via Python `urllib` and downloads clean, uncropped EAZY plots directly into `venus_eazy/`.

### 3. Adding a New Cluster Field
When adding a new cluster:
1. Create directory `<CLUSTER_NAME>/RELICS/`.
2. Follow the PG004 pattern with catalog inputs, crossmatching, and HTML generator.
3. Update root `index.html` to add a new card in the cluster grid.
4. Commit and push:
   ```bash
   git add .
   git commit -m "Add cluster <CLUSTER_NAME>"
   git push
   ```

---

## 🎨 UI Guidelines

* Always retain the **`22 High-z Sample`** quick reset button.
* Ensure all links to RELICS STScI pages and live VENUS Hub pages open in `target="_blank"` with `rel="noreferrer"`.
* Keep the design clean, responsive, and using the established editorial color palette (`--ink`, `--paper`, `--cyan`, `--coral`, `--yellow`).
