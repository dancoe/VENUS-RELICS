#!/usr/bin/env python3
"""Generate or serve the interactive RELICS-VENUS evidence browser.

Supports:
- CLI generation of default or subset pages by RELICS ID, JWST ID, or coords
- Dynamic on-the-fly crossmatching against full catalogs
- Automated fetching & caching of authenticated VENUS EAZY plots
- Built-in lightweight local web server with live search & filtering UI
"""

import argparse
import csv
import html
import http.cookiejar
import http.server
import json
import math
from pathlib import Path
import socketserver
import sys
import urllib.parse
import urllib.request
import webbrowser

import astropy.units as u
from astropy.coordinates import SkyCoord


DEFAULT_CROSSMATCH = Path("relics_jwst_coordinate_match.csv")
RELICS_FULL_CAT = Path("plckg004-19.cat")
JWST_FULL_CSV = Path("pg004_aphot_cut_wzphots.csv")
DEFAULT_OUTPUT = Path("RELICS_VENUS.html")
EAZY_CACHE_DIR = Path("venus_eazy")

RELICS_BASE = "https://relics.stsci.edu/HST/plckg004-19/final_processing/catalogs/IR_detection/PhotoZ/html"
VENUS_BASE = "https://venushub.astro.utoronto.ca/clusters/PG004"

DEFAULT_RA_OFFSET_ARCSEC = 0.536463
DEFAULT_DEC_OFFSET_ARCSEC = -0.001390


def esc(value):
    return html.escape(str(value if value is not None else ""), quote=True)


def number(value, digits=3):
    try:
        val = float(value)
        if math.isnan(val) or not math.isfinite(val):
            return "--"
        return f"{val:.{digits}f}"
    except (TypeError, ValueError):
        return "--"


def sexagesimal_ra(value):
    try:
        return SkyCoord(ra=float(value) * u.deg, dec=0 * u.deg).ra.to_string(
            unit=u.hourangle, sep=":", precision=2, pad=True
        )
    except Exception:
        return str(value)


def sexagesimal_dec(value):
    try:
        return SkyCoord(ra=0 * u.deg, dec=float(value) * u.deg).dec.to_string(
            unit=u.deg, sep=":", precision=2, pad=True, alwayssign=True
        )
    except Exception:
        return str(value)


def ensure_eazy_plot(jwst_id, name="Dan Coe", password="l3nsing!"):
    """Ensure that the local cached EAZY SED plot exists; downloads if missing."""
    EAZY_CACHE_DIR.mkdir(exist_ok=True)
    target_path = EAZY_CACHE_DIR / f"venus_eazy_{jwst_id}.png"
    if target_path.exists() and target_path.stat().st_size > 1000:
        return target_path

    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    try:
        login_data = urllib.parse.urlencode({
            "name": name,
            "password": password,
            "next": "/"
        }).encode("utf-8")
        login_req = urllib.request.Request("https://venushub.astro.utoronto.ca/login", data=login_data, method="POST")
        opener.open(login_req, timeout=10)

        img_url = f"https://venushub.astro.utoronto.ca/clusters/PG004/eazy/{jwst_id}.png"
        img_req = urllib.request.Request(img_url)
        with opener.open(img_req, timeout=10) as resp:
            content = resp.read()
            if len(content) > 1000 and resp.headers.get("Content-Type", "").startswith("image/"):
                target_path.write_bytes(content)
                return target_path
    except Exception as e:
        print(f"Warning: Could not fetch VENUS EAZY image for ID {jwst_id}: {e}", file=sys.stderr)
    return target_path


def load_precomputed_crossmatch(csv_path=DEFAULT_CROSSMATCH):
    if not csv_path.exists():
        return []
    with csv_path.open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    return [
        {
            **row,
            "relics_match_id": row.get("hst_ID") or row.get("relics_match_id", ""),
            "relics_zb": row.get("hst_zbpz") or row.get("relics_zb", ""),
            "relics_zbmin": row.get("hst_zbmin") or row.get("relics_zbmin", ""),
            "relics_zbmax": row.get("hst_zbmax") or row.get("relics_zbmax", ""),
            "relics_stel": row.get("hst_stellarity") or row.get("relics_stel", ""),
            "relics_odds": row.get("hst_odds") or row.get("relics_odds", ""),
            "jwst_id": row.get("jwst_id") or row.get("jwst_match_id", ""),
            "jwst_ra": row.get("jwst_ra", ""),
            "jwst_dec": row.get("jwst_dec", ""),
            "jwst_z_phot": row.get("jwst_z_phot", ""),
            "jwst_z025": row.get("jwst_z025", ""),
            "jwst_z975": row.get("jwst_z975", ""),
            "corrected_separation_arcsec": row.get("corrected_separation_arcsec", ""),
        }
        for row in rows
        if row.get("match_status", "matched") == "matched"
    ]


def read_relics_full_cat(path=RELICS_FULL_CAT):
    if not path.exists():
        return {}, []
    lines = path.read_text().splitlines()
    header_line = next((l for l in lines if l.startswith("##  id")), None)
    if not header_line:
        return {}, []
    fields = header_line[2:].split()
    rows = []
    for l in lines:
        if not l or l.startswith("#"):
            continue
        vals = l.split()
        if len(vals) == len(fields):
            rows.append(dict(zip(fields, vals)))
    return {r["id"]: r for r in rows}, rows


def read_jwst_full_csv(path=JWST_FULL_CSV):
    if not path.exists():
        return {}, []
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    return {r["id"]: r for r in rows}, rows


def calc_separation(ra1, dec1, ra2, dec2, ra_shift=DEFAULT_RA_OFFSET_ARCSEC, dec_shift=DEFAULT_DEC_OFFSET_ARCSEC):
    hst_dec = dec2 + dec_shift / 3600.0
    mean_dec = (hst_dec + dec1) / 2.0
    d_ra = (ra1 - ra2) * math.cos(math.radians(mean_dec)) * 3600.0 - ra_shift
    d_dec = (dec1 - hst_dec) * 3600.0
    return math.hypot(d_ra, d_dec)


def match_ids_dynamic(relics_ids=None, venus_ids=None, match_radius=0.5):
    """Dynamically match requested IDs against the full catalogs."""
    relics_dict, relics_list = read_relics_full_cat()
    jwst_dict, jwst_list = read_jwst_full_csv()

    results = []
    seen = set()

    if venus_ids:
        for vid in venus_ids:
            vid_str = str(vid).strip()
            if not vid_str or vid_str in seen:
                continue
            seen.add(vid_str)
            if vid_str in jwst_dict and relics_list:
                j_row = jwst_dict[vid_str]
                j_ra, j_dec = float(j_row["ra"]), float(j_row["dec"])
                best_relics = min(
                    relics_list,
                    key=lambda r: calc_separation(j_ra, j_dec, float(r["RA"]), float(r["Dec"]))
                )
                sep = calc_separation(j_ra, j_dec, float(best_relics["RA"]), float(best_relics["Dec"]))
                results.append({
                    "match_status": "matched" if sep <= match_radius else "candidate",
                    "jwst_id": vid_str,
                    "relics_match_id": best_relics["id"],
                    "jwst_ra": j_row["ra"],
                    "jwst_dec": j_row["dec"],
                    "jwst_z_phot": j_row.get("z_phot", ""),
                    "jwst_z025": j_row.get("z025", ""),
                    "jwst_z975": j_row.get("z975", ""),
                    "relics_zb": best_relics.get("zb", ""),
                    "relics_zbmin": best_relics.get("zbmin", ""),
                    "relics_zbmax": best_relics.get("zbmax", ""),
                    "relics_stel": best_relics.get("stel", ""),
                    "relics_odds": best_relics.get("odds", ""),
                    "corrected_separation_arcsec": f"{sep:.4f}",
                })

    if relics_ids:
        for rid in relics_ids:
            rid_str = str(rid).strip()
            if not rid_str:
                continue
            if rid_str in relics_dict and jwst_list:
                r_row = relics_dict[rid_str]
                r_ra, r_dec = float(r_row["RA"]), float(r_row["Dec"])
                best_jwst = min(
                    jwst_list,
                    key=lambda j: calc_separation(float(j["ra"]), float(j["dec"]), r_ra, r_dec)
                )
                sep = calc_separation(float(best_jwst["ra"]), float(best_jwst["dec"]), r_ra, r_dec)
                if best_jwst["id"] not in seen:
                    seen.add(best_jwst["id"])
                    results.append({
                        "match_status": "matched" if sep <= match_radius else "candidate",
                        "jwst_id": best_jwst["id"],
                        "relics_match_id": rid_str,
                        "jwst_ra": best_jwst["ra"],
                        "jwst_dec": best_jwst["dec"],
                        "jwst_z_phot": best_jwst.get("z_phot", ""),
                        "jwst_z025": best_jwst.get("z025", ""),
                        "jwst_z975": best_jwst.get("z975", ""),
                        "relics_zb": r_row.get("zb", ""),
                        "relics_zbmin": r_row.get("zbmin", ""),
                        "relics_zbmax": r_row.get("zbmax", ""),
                        "relics_stel": r_row.get("stel", ""),
                        "relics_odds": r_row.get("odds", ""),
                        "corrected_separation_arcsec": f"{sep:.4f}",
                    })

    return results


def target_card(row, index):
    jwst_id = str(row.get("jwst_id", "")).strip()
    relics_id = str(row.get("relics_match_id", "")).strip()
    relics_page = f"{RELICS_BASE}/{relics_id}.html"
    venus_page = f"{VENUS_BASE}/source/{jwst_id}"
    color_image = f"{RELICS_BASE}/colorstamps/ACSIR/stamp{relics_id}.png"
    relics_sed = f"{RELICS_BASE}/sedplots/photometry_sed_{relics_id}.png"
    relics_pz = f"{RELICS_BASE}/probplots/withEazy/probplot_{relics_id}.png"
    venus_eazy = f"{VENUS_BASE}/eazy/{jwst_id}.png?version=v0.2"
    venus_eazy_local = f"venus_eazy/venus_eazy_{jwst_id}.png"

    try:
        relics_zb = float(row.get("relics_zb") or -1)
        relics_zbmin = float(row.get("relics_zbmin") or -1)
    except Exception:
        relics_zb, relics_zbmin = -1, -1

    if relics_zb >= 6 and relics_zbmin >= 4.5:
        agreement_label = "strict HST high-z agreement"
    elif relics_zb >= 6:
        agreement_label = "RELICS BPZ high-z match"
    else:
        agreement_label = "matched HST source"

    return f"""
    <article class="target" id="target-{esc(jwst_id)}" data-jwst="{esc(jwst_id)}" data-relics="{esc(relics_id)}">
      <div class="target-heading">
        <div>
          <p class="eyebrow">Target {index:02d} · {agreement_label}</p>
          <h2><a class="venus-id" href="{esc(venus_page)}" target="_blank" rel="noreferrer">VENUS <span>{esc(jwst_id)}</span></a> <small>↔</small> <a class="relics-id" href="{esc(relics_page)}" target="_blank" rel="noreferrer">RELICS <span>{esc(relics_id)}</span></a></h2>
          <p class="coordinates"><strong>RA {sexagesimal_ra(row.get('jwst_ra', 0))}</strong> <span>({number(row.get('jwst_ra', 0), 6)}°)</span><b>·</b><strong>Dec {sexagesimal_dec(row.get('jwst_dec', 0))}</strong> <span>({number(row.get('jwst_dec', 0), 6)}°)</span></p>
        </div>
      </div>

      <dl class="redshift-summary">
        <div><dt>JWST VENUS</dt><dd>z = {number(row.get('jwst_z_phot'), 3)} <span>[{number(row.get('jwst_z025'), 3)} – {number(row.get('jwst_z975'), 3)}]</span> <em>(95%)</em></dd></div>
        <div><dt>HST RELICS</dt><dd>z = {number(row.get('relics_zb'), 3)} <span>[{number(row.get('relics_zbmin'), 3)} – {number(row.get('relics_zbmax'), 3)}]</span> <em>(95%)</em> <b class="inline-fact">stellarity {number(row.get('relics_stel'), 2)} · match {number(row.get('corrected_separation_arcsec'), 3)}&Prime;</b></dd></div>
      </dl>

      <div class="evidence-stack">
        <section class="evidence evidence-color">
          <div class="evidence-label"><span>01</span><div><strong>RELICS HST color image</strong><small>ACS + IR color stamp · HST source {esc(relics_id)}</small></div></div>
          <a href="{esc(color_image)}" target="_blank" rel="noreferrer"><img src="{esc(color_image)}" alt="RELICS HST ACS and infrared color image for source {esc(relics_id)}" loading="lazy"></a>
        </section>
        <section class="evidence evidence-relics">
          <div class="evidence-label"><span>02–03</span><div><strong>RELICS BPZ SED + P(z)</strong><small>HST photometry, BPZ model, and redshift probability</small></div></div>
          <div class="relics-plots">
            <a href="{esc(relics_sed)}" target="_blank" rel="noreferrer"><img src="{esc(relics_sed)}" alt="RELICS BPZ photometry SED for source {esc(relics_id)}" loading="lazy"></a>
            <a href="{esc(relics_pz)}" target="_blank" rel="noreferrer"><img src="{esc(relics_pz)}" alt="RELICS BPZ redshift probability plot for source {esc(relics_id)}" loading="lazy"></a>
          </div>
        </section>
        <section class="evidence evidence-wide venus-evidence">
          <div class="evidence-label"><span>04</span><div><strong>VENUS EAZY SED + P(z)</strong><small>VENUS v0.2 source {esc(jwst_id)} · direct EAZY SED and posterior</small></div></div>
          <a href="{esc(venus_eazy)}" target="_blank" rel="noreferrer"><img class="venus-panel" src="{esc(venus_eazy_local)}" alt="VENUS EAZY SED and redshift probability plot for source {esc(jwst_id)}" loading="lazy" onerror="this.onerror=null; this.src='{esc(venus_eazy)}';"></a>
          <a class="asset-link" href="{esc(venus_page)}" target="_blank" rel="noreferrer">Open VENUS source page directly ↗</a>
          <p class="asset-note">Plot served locally from VENUS EAZY assets; the link opens the live VENUS interactive source page.</p>
        </section>
      </div>
    </article>
    """


def build_page(rows, title="RELICS × VENUS · HST high-z matches", is_app=False):
    cards = "\n".join(target_card(row, index) for index, row in enumerate(rows, 1))
    highz_count = sum(float(row.get("relics_zb") or 0) >= 6 for row in rows)
    strict_count = sum(float(row.get("relics_zb") or 0) >= 6 and float(row.get("relics_zbmin") or 0) >= 4.5 for row in rows)
    nav = "\n".join(
        f'<a href="#target-{esc(row["jwst_id"])}" data-jwst="{esc(row["jwst_id"])}" data-relics="{esc(row["relics_match_id"])}"><span>{index:02d}</span>VENUS {esc(row["jwst_id"])} <b>↔</b> RELICS {esc(row["relics_match_id"])}</a>'
        for index, row in enumerate(rows, 1)
    )

    app_bar = """
    <div class="search-bar-container">
      <div class="search-bar">
        <label for="id-search">🔍 Quick Filter / Lookup IDs:</label>
        <input type="text" id="id-search" placeholder="Type VENUS or RELICS ID (e.g. 5545, 222, 1600)..." autocomplete="off">
        <button id="clear-btn" type="button">Clear</button>
      </div>
      <div class="search-hint">Interactive client filter enabled · Matches instant typing or comma-separated lists</div>
    </div>
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <style>
    :root {{
      --ink: #15262b;
      --muted: #607477;
      --paper: #f4f1e9;
      --panel: #fffdf8;
      --line: #d8ddd5;
      --cyan: #007f86;
      --yellow: #f2c94c;
      --coral: #c95d4e;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{ margin: 0; color: var(--ink); background: var(--paper); font-family: Georgia, 'Times New Roman', serif; }}
    body::before {{ content: ''; position: fixed; inset: 0; pointer-events: none; opacity: .28; background-image: linear-gradient(135deg, rgba(0,127,134,.06) 25%, transparent 25%), linear-gradient(315deg, rgba(201,93,78,.035) 25%, transparent 25%); background-size: 34px 34px; z-index: -1; }}
    a {{ color: inherit; }}
    .masthead {{ border-bottom: 1px solid var(--line); background: rgba(244,241,233,.94); }}
    .masthead-inner {{ width: 100%; padding: 34px 34px 28px; display: flex; gap: 36px; justify-content: space-between; align-items: end; }}
    .kicker, .eyebrow, .evidence-label, dt {{ font-family: 'Helvetica Neue', Helvetica, sans-serif; letter-spacing: .08em; text-transform: uppercase; }}
    .kicker {{ color: var(--cyan); font-size: 11px; font-weight: 700; margin: 0 0 12px; }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ font-size: clamp(34px, 5vw, 68px); line-height: .95; letter-spacing: -.025em; margin-bottom: 14px; font-weight: 500; max-width: 720px; }}
    .dek {{ max-width: 760px; color: var(--muted); font-size: 17px; line-height: 1.55; margin-bottom: 0; }}
    .count-block {{ min-width: 180px; text-align: right; font-family: 'Helvetica Neue', Helvetica, sans-serif; }}
    .count {{ color: var(--coral); font-size: 50px; line-height: .85; font-weight: 700; }}
    .count-label {{ color: var(--muted); font-size: 11px; letter-spacing: .1em; text-transform: uppercase; margin-top: 10px; }}
    
    .search-bar-container {{ padding: 18px 34px; background: #eaedf0; border-bottom: 1px solid var(--line); }}
    .search-bar {{ display: flex; gap: 14px; align-items: center; max-width: 900px; }}
    .search-bar label {{ font-family: 'Helvetica Neue', sans-serif; font-size: 13px; font-weight: 700; color: var(--ink); white-space: nowrap; }}
    .search-bar input {{ flex: 1; padding: 10px 14px; font-size: 15px; border: 1px solid var(--line); border-radius: 4px; background: #fff; }}
    .search-bar button {{ padding: 10px 18px; font-size: 13px; font-weight: 600; border: none; border-radius: 4px; background: var(--cyan); color: #fff; cursor: pointer; }}
    .search-bar button:hover {{ background: #00686e; }}
    .search-hint {{ font-size: 11px; color: var(--muted); font-family: 'Helvetica Neue', sans-serif; margin-top: 6px; }}

    .layout {{ width: 100%; padding: 28px 34px 80px; display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 34px; }}
    .index {{ position: sticky; top: 18px; align-self: start; border-top: 3px solid var(--ink); padding-top: 13px; max-height: calc(100vh - 40px); overflow-y: auto; }}
    .index-title {{ font-family: 'Helvetica Neue', Helvetica, sans-serif; font-size: 11px; letter-spacing: .1em; text-transform: uppercase; color: var(--muted); margin: 0 0 10px; }}
    .index a {{ display: block; padding: 10px 0; border-bottom: 1px solid var(--line); text-decoration: none; font-size: 14px; }}
    .index a:hover {{ color: var(--cyan); }}
    .index a.hidden, .target.hidden {{ display: none !important; }}
    .index span {{ color: var(--coral); font-family: 'Helvetica Neue', Helvetica, sans-serif; font-size: 11px; margin-right: 8px; }}
    .index b {{ color: var(--muted); padding: 0 3px; }}
    .target {{ background: var(--panel); border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); margin-bottom: 34px; scroll-margin-top: 18px; }}
    .target-heading {{ padding: 20px 26px 16px; border-bottom: 1px solid var(--line); }}
    .eyebrow {{ color: var(--coral); font-size: 10px; font-weight: 700; margin-bottom: 8px; }}
    h2 {{ font-size: clamp(22px, 3vw, 34px); line-height: 1; font-weight: 500; margin-bottom: 0; }}
    h2 span {{ color: var(--cyan); }}
    h2 small {{ color: var(--yellow); font-size: .8em; padding: 0 5px; }}
    h2 a {{ text-decoration: none; }}
    h2 a:hover {{ text-decoration: underline; text-decoration-thickness: 2px; text-underline-offset: 5px; }}
    .venus-id {{ color: var(--ink); }}
    .relics-id {{ color: var(--cyan); }}
    .redshift-summary {{ display: grid; grid-template-columns: 1fr; margin: 0; border-bottom: 1px solid var(--line); }}
    .redshift-summary div {{ padding: 12px 16px; border-bottom: 1px solid var(--line); min-width: 0; }}
    .redshift-summary div:last-child {{ border-bottom: 0; }}
    .redshift-summary dd {{ font-size: 18px; white-space: normal; }}
    .redshift-summary dd span {{ color: var(--cyan); }}
    .redshift-summary dd em {{ display: inline; color: var(--muted); font-size: 10px; margin-left: 3px; }}
    .inline-fact {{ color: var(--muted); font: 11px 'Helvetica Neue', Helvetica, sans-serif; font-weight: 500; margin-left: 14px; white-space: nowrap; }}
    dt {{ color: var(--muted); font-size: 9px; font-weight: 700; margin-bottom: 6px; }}
    dd {{ margin: 0; font-family: 'Helvetica Neue', Helvetica, sans-serif; font-size: 16px; font-weight: 700; white-space: nowrap; }}
    dd em {{ display: block; color: var(--coral); font-size: 9px; font-style: normal; letter-spacing: .04em; text-transform: uppercase; margin-top: 3px; }}
    .coordinates {{ color: var(--muted); font-family: 'Helvetica Neue', Helvetica, sans-serif; font-size: 12px; letter-spacing: .01em; margin: 12px 0 0; }}
    .coordinates strong {{ color: var(--ink); font-size: 16px; font-weight: 700; }}
    .coordinates span {{ font-size: 10px; }}
    .coordinates b {{ color: var(--yellow); padding: 0 8px; }}
    .evidence-stack {{ padding: 20px 26px 24px; border-top: 1px solid var(--line); display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) minmax(0, 2fr); gap: 14px; }}
    .evidence {{ min-width: 0; padding: 0; }}
    .evidence-color {{ grid-column: 1; grid-row: 1 / span 2; }}
    .evidence-relics {{ grid-column: 2; grid-row: 1 / span 2; }}
    .relics-plots {{ display: grid; gap: 14px; }}
    .venus-evidence {{ grid-column: 3; grid-row: 1 / span 2; }}
    .evidence-label {{ display: flex; gap: 12px; align-items: start; margin-bottom: 13px; font-size: 11px; }}
    .evidence-label > span {{ color: var(--coral); font-size: 12px; font-weight: 700; }}
    .evidence-label strong {{ display: block; font-size: 11px; color: var(--ink); }}
    .evidence-label small {{ display: block; color: var(--muted); font: 12px Georgia, serif; letter-spacing: 0; text-transform: none; margin-top: 3px; }}
    .evidence img {{ display: block; max-width: 100%; height: auto; margin: auto; border: 1px solid #e0e3dd; background: #fff; }}
    .evidence-color img {{ width: 83.333%; }}
    .evidence-wide img {{ width: 100%; }}
    .venus-panel {{ display: block; width: 100%; height: auto; margin: auto; border: 1px solid #e0e3dd; background: #fff; }}
    .evidence a {{ display: block; }}
    .evidence .asset-link {{ color: var(--cyan); font: 10px 'Helvetica Neue', Helvetica, sans-serif; margin: 8px auto 0; text-decoration: none; }}
    .evidence .asset-link:hover {{ text-decoration: underline; }}
    .venus-evidence {{ background: #f7faf6; }}
    .asset-note {{ color: var(--muted); font: 12px/1.5 'Helvetica Neue', Helvetica, sans-serif; margin: 12px auto 0; max-width: 1100px; }}
    .footer {{ width: 100%; padding: 0 34px 34px; color: var(--muted); font: 12px/1.6 'Helvetica Neue', Helvetica, sans-serif; }}
    @media (max-width: 920px) {{
      .masthead-inner {{ display: block; padding: 26px 20px; }}
      .count-block {{ text-align: left; margin-top: 24px; }}
      .layout {{ display: block; padding: 20px 14px 50px; }}
      .index {{ position: static; margin-bottom: 20px; max-height: none; }}
      .index a {{ display: inline-block; margin-right: 12px; border-bottom: 0; }}
      .target-heading {{ display: block; padding: 18px 16px 14px; }}
      .coordinates {{ line-height: 1.5; }}
      .inline-fact {{ display: block; margin: 5px 0 0; }}
      .evidence-stack {{ grid-template-columns: minmax(145px, 1fr) minmax(145px, 1fr) minmax(290px, 2fr); overflow-x: auto; padding-left: 16px; padding-right: 16px; }}
      .footer {{ padding: 0 14px 30px; }}
    }}
  </style>
</head>
<body>
  <header class="masthead">
    <div class="masthead-inner">
      <div>
        <p class="kicker">PG004 · evidence browser</p>
        <h1>RELICS × VENUS<br>HST high-z matches</h1>
        <p class="dek">Displaying {len(rows)} targets. <strong>{highz_count}</strong> have RELICS BPZ <strong>z ≥ 6</strong>, including <strong>{strict_count}</strong> with a conservative <strong>95% lower bound ≥ 4.5</strong>. HST color, RELICS BPZ evidence, and authenticated VENUS EAZY panels are shown side-by-side.</p>
      </div>
      <div class="count-block"><div class="count">{len(rows):02d}</div><div class="count-label">targets loaded<br>{strict_count:02d} strict high-z agreements</div></div>
    </div>
  </header>
  {app_bar}
  <main class="layout">
    <nav class="index" aria-label="Matched target index">
      <p class="index-title">Targets (<span id="visible-count">{len(rows)}</span>)</p>
      {nav}
    </nav>
    <section id="cards-container">
      {cards}
    </section>
  </main>
  <footer class="footer">
    Coordinate residuals use global astrometric offset: VENUS − HST = +0.536463 arcsec in projected RA and −0.001390 arcsec in Dec. Generated by <a href="make_relics_venus_html.py">make_relics_venus_html.py</a>.
  </footer>

  <script>
    const searchInput = document.getElementById('id-search');
    const clearBtn = document.getElementById('clear-btn');
    const visibleCount = document.getElementById('visible-count');
    const targets = Array.from(document.querySelectorAll('.target'));
    const navLinks = Array.from(document.querySelectorAll('.index a'));

    function filterTargets() {{
      const query = (searchInput.value || '').trim().toLowerCase();
      if (!query) {{
        targets.forEach(t => t.classList.remove('hidden'));
        navLinks.forEach(n => n.classList.remove('hidden'));
        visibleCount.textContent = targets.length;
        return;
      }}
      const tokens = query.split(/[\s,]+/).filter(Boolean);
      let count = 0;

      targets.forEach((target, i) => {{
        const jwst = (target.dataset.jwst || '').toLowerCase();
        const relics = (target.dataset.relics || '').toLowerCase();
        const match = tokens.some(t => jwst.includes(t) || relics.includes(t));
        if (match) {{
          target.classList.remove('hidden');
          navLinks[i].classList.remove('hidden');
          count++;
        }} else {{
          target.classList.add('hidden');
          navLinks[i].classList.add('hidden');
        }}
      }});
      visibleCount.textContent = count;
    }}

    if (searchInput) {{
      searchInput.addEventListener('input', filterTargets);
      clearBtn.addEventListener('click', () => {{
        searchInput.value = '';
        filterTargets();
        searchInput.focus();
      }});
    }}
  </script>
</body>
</html>"""


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/search":
            query_params = urllib.parse.parse_qs(parsed.query)
            venus_ids = query_params.get("venus_id", [])
            relics_ids = query_params.get("relics_id", [])
            
            # Support comma-separated strings
            v_list = []
            for v in venus_ids:
                v_list.extend(v.split(","))
            r_list = []
            for r in relics_ids:
                r_list.extend(r.split(","))

            matched_rows = match_ids_dynamic(relics_ids=r_list, venus_ids=v_list)
            for row in matched_rows:
                ensure_eazy_plot(row["jwst_id"])

            html_content = build_page(matched_rows, title="RELICS × VENUS Search Results", is_app=True)
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.send_header("Content-length", str(len(html_content.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))
            return

        super().do_GET()


def run_server(port=8000):
    handler = CustomHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        url = f"http://localhost:{port}/RELICS_VENUS.html"
        print(f"🚀 Serving interactive RELICS × VENUS app at: {url}")
        print(f"📡 API Query Endpoint: http://localhost:{port}/api/search?venus_id=5545,1600&relics_id=222")
        print("Press Ctrl+C to stop the server.")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate or serve interactive RELICS-VENUS HST-high-z evidence browser."
    )
    parser.add_argument(
        "--relics-ids", type=str, nargs="+",
        help="One or more RELICS HST IDs (e.g. --relics-ids 222 1983 2057)"
    )
    parser.add_argument(
        "--venus-ids", type=str, nargs="+",
        help="One or more JWST VENUS IDs (e.g. --venus-ids 5545 1801 1600)"
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help=f"Output HTML file path (default: {DEFAULT_OUTPUT})"
    )
    parser.add_argument(
        "--fetch-eazy", action="store_true", default=True,
        help="Automatically fetch & cache authenticated VENUS EAZY plot images (default: True)"
    )
    parser.add_argument(
        "--serve", action="store_true",
        help="Launch interactive local web server with live search & filtering"
    )
    parser.add_argument(
        "--port", type=int, default=8000,
        help="Port for local web server (default: 8000)"
    )

    args = parser.parse_args()

    # If --serve is requested, build default page first and start server
    if args.serve:
        rows = load_precomputed_crossmatch()
        args.output.write_text(build_page(rows, is_app=True), encoding="utf-8")
        run_server(args.port)
        return

    # Check if specific IDs were requested
    if args.relics_ids or args.venus_ids:
        r_ids = []
        if args.relics_ids:
            for item in args.relics_ids:
                r_ids.extend(item.replace(",", " ").split())
        v_ids = []
        if args.venus_ids:
            for item in args.venus_ids:
                v_ids.extend(item.replace(",", " ").split())

        print(f"Performing dynamic match for RELICS IDs: {r_ids}, VENUS IDs: {v_ids}...")
        rows = match_ids_dynamic(relics_ids=r_ids, venus_ids=v_ids)
        title = f"RELICS × VENUS · Custom Subset ({len(rows)} sources)"
    else:
        rows = load_precomputed_crossmatch()
        title = "RELICS × VENUS · HST high-z matches"

    # Ensure EAZY plots are downloaded
    if args.fetch_eazy:
        for r in rows:
            jid = r.get("jwst_id")
            if jid:
                ensure_eazy_plot(jid)

    html_text = build_page(rows, title=title, is_app=True)
    args.output.write_text(html_text, encoding="utf-8")
    print(f"✅ Successfully wrote {args.output} with {len(rows)} targets.")


if __name__ == "__main__":
    main()
