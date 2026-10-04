"""Build data/zips.json: NC zip code -> [lat, lng], from the US Census ZCTA gazetteer.

Runs once (the workflow skips it when the file exists). The site uses it to
turn a typed zip code into a point and sort stores by distance.
"""
import io
import json
import os
import re
import sys
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "zips.json")
YEARS = [2025, 2024, 2023]
URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/{y}_Gazetteer/{y}_Gaz_zcta_national.zip"


def main():
    for y in YEARS:
        try:
            r = requests.get(URL.format(y=y), timeout=120)
        except requests.RequestException as e:
            print(f"{y}: {e}")
            continue
        if r.status_code != 200:
            print(f"{y}: HTTP {r.status_code}")
            continue
        try:
            out = parse(r.content)
        except Exception as e:  # header layout changed, bad zip, etc.
            print(f"{y}: could not parse gazetteer: {e}")
            continue
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        print(f"zips.json: {len(out)} NC zip codes from {y} gazetteer")
        return
    # Not fatal: the site falls back to sorting stores by zip number.
    print("WARNING: no zip table built; the site will sort stores by zip number instead")


def parse(blob: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(blob))
    name = next(n for n in z.namelist() if n.lower().endswith((".txt", ".csv")))
    text = z.read(name).decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    delim = max(["\t", "|", ","], key=lines[0].count)
    hdr = [h.strip().strip('"').upper() for h in lines[0].split(delim)]

    def col(*keys):
        for k in keys:
            for i, h in enumerate(hdr):
                if k in h:
                    return i
        raise ValueError(f"none of {keys} in header {hdr}")

    gi, la, lo = col("GEOID", "ZCTA"), col("INTPTLAT"), col("INTPTLONG", "INTPTLON")
    out = {}
    for line in lines[1:]:
        f = [x.strip().strip('"') for x in line.split(delim)]
        if len(f) <= max(gi, la, lo):
            continue
        z5 = re.sub(r"\D", "", f[gi])[-5:]
        if z5[:2] in ("27", "28"):
            out[z5] = [round(float(f[la]), 4), round(float(f[lo]), 4)]
    if len(out) < 500:
        raise ValueError(f"only {len(out)} NC zip codes found")
    return out


if __name__ == "__main__":
    main()
