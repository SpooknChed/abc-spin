"""Build data/zips.json: NC zip code -> [lat, lng], from the US Census ZCTA gazetteer.

Runs once (the workflow skips it when the file exists). The site uses it to
turn a typed zip code into a point and sort stores by distance.
"""
import io
import json
import os
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
        z = zipfile.ZipFile(io.BytesIO(r.content))
        text = z.read(z.namelist()[0]).decode("utf-8", errors="replace")
        lines = text.splitlines()
        hdr = [h.strip() for h in lines[0].split("\t")]
        gi, la, lo = hdr.index("GEOID"), hdr.index("INTPTLAT"), hdr.index("INTPTLONG")
        out = {}
        for line in lines[1:]:
            f = [x.strip() for x in line.split("\t")]
            if f[gi][:2] in ("27", "28"):
                out[f[gi]] = [round(float(f[la]), 4), round(float(f[lo]), 4)]
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w") as fh:
            json.dump(out, fh, separators=(",", ":"))
        print(f"zips.json: {len(out)} NC zip codes from {y} gazetteer")
        return
    sys.exit("Could not download the Census ZCTA gazetteer")


if __name__ == "__main__":
    main()
