"""Daily ABC Spin data build for Wake County.

1. Statewide catalog from the NC ABC Commission price list export (proof, size, supplier).
2. Wake County store list from the store locator feed (ids, coordinates, hours).
3. Wake per-store stock from the public inventory search: keyword sweeps first,
   then one search per NC code the sweeps missed. About 1 request per second.

Writes into data/:
  meta.json                 when the run finished and what it found
  stores.json               [{id, name, address, city, zip, lat, lng, phone, hours}]
  products.json             {code: {name, type, sizeMl, proof, price}}
  inventory/<storeId>.json  [[code, qty], ...]   only products in stock
  unclassified.txt          product names typed "Other", for tuning classify.py

Nothing in data/ is replaced unless the run looks healthy, so a bad night
leaves yesterday's data in place.

Usage:
  python scraper/scrape.py                  full run
  python scraper/scrape.py --limit 50       quick test: sweeps skipped, 50 codes
"""
import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(__file__))
from classify import classify  # noqa: E402
from stores import ADDRESS_TO_ID, EXCLUDE_IDS, LOCATOR_URL, clean_store, norm_addr  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OVERRIDES = os.path.join(os.path.dirname(__file__), "overrides.json")

PRICE_LIST = "https://abc2.nc.gov/Pricing/PriceList"
PRICE_EXPORT = "https://abc2.nc.gov/Pricing/ExportData"
WAKE_SEARCH = "https://wakeabc.com/search-results"

# Wake's search matches substrings, so short words like "gin" or "rum" would also hit
# "original" or "drum" and risk a timeout. Those products get picked up per-code instead.
SWEEP_TERMS = [
    "vodka", "bourbon", "whiskey", "whisky", "scotch", "tequila", "mezcal",
    "brandy", "cognac", "liqueur", "schnapps",
]
DELAY = 1.0          # seconds between Wake requests
TIMEOUT = 90         # keyword sweeps can take ~20 s
UA = "ABC-Spin inventory bot (personal project; 1 req/s; github.com)"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def session():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    return s


# ---------------------------------------------------------------- catalog
def size_ml(text: str) -> int | None:
    t = text.strip().upper()
    m = re.match(r"^([\d.]+)\s*(ML|L)$", t)
    if not m:
        return None
    v = float(m.group(1))
    return round(v * 1000) if m.group(2) == "L" else round(v)


def money(text: str) -> float | None:
    m = re.search(r"[\d,]+\.?\d*", text or "")
    return float(m.group(0).replace(",", "")) if m else None


def parse_catalog_csv(text: str) -> dict:
    out = {}
    for row in csv.DictReader(io.StringIO(text)):
        code = (row.get("NC Code") or "").strip()
        if not code:
            continue
        code = code.zfill(5)
        proof = (row.get("Proof") or "").strip()
        out[code] = {
            "name": (row.get("Brand Name") or "").strip(),
            "supplier": (row.get("Supplier") or "").strip(),
            "proof": float(proof) if re.fullmatch(r"[\d.]+", proof) else None,
            "sizeMl": size_ml(row.get("Bottle Size") or ""),
            "price": money(row.get("Retail Bottle Price")),
        }
    return out


def fetch_catalog(s) -> dict:
    page = s.get(PRICE_LIST, timeout=60)
    page.raise_for_status()
    token = BeautifulSoup(page.text, "html.parser").find("input", {"name": "__RequestVerificationToken"})
    extra = {"__RequestVerificationToken": token["value"]} if token else {}
    s.post(PRICE_LIST, data={"NCCode": "", "BrandName": "", **extra}, timeout=120).raise_for_status()
    r = s.post(PRICE_EXPORT, data=extra, timeout=120)
    r.raise_for_status()
    cat = parse_catalog_csv(r.content.decode("utf-8-sig", errors="replace"))
    log(f"catalog: {len(cat)} products")
    return cat


# ---------------------------------------------------------------- stores
def fetch_stores(s) -> list:
    r = s.get(LOCATOR_URL, timeout=60)
    r.raise_for_status()
    stores = [clean_store(x) for x in r.json() if int(x["id"]) not in EXCLUDE_IDS]
    stores.sort(key=lambda x: int(re.sub(r"\D", "", x["name"]) or 0))
    log(f"stores: {len(stores)}")
    return stores


# ---------------------------------------------------------------- inventory
def parse_results(html: str) -> list:
    """Return [{code, name, price, sizeMl, stock: {address_line: qty}}] from a Wake results page."""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for p in soup.select(".wake-product"):
        small = p.find("small")
        code = re.sub(r"\D", "", small.get_text()) if small else ""
        if not code:
            continue
        stock = {}
        for li in p.select("li"):
            addr = li.select_one(".address")
            qty = li.select_one(".quantity")
            if not addr or not qty:
                continue
            first_line = addr.get_text("\n").split("\n")[0]
            m = re.search(r"\d+", qty.get_text())
            stock[norm_addr(first_line)] = int(m.group(0)) if m else 0
        price = p.select_one(".price")
        size = p.select_one(".size")
        out.append({
            "code": code.zfill(5),
            "name": p.find("h4").get_text(strip=True) if p.find("h4") else "",
            "price": money(price.get_text()) if price else None,
            "sizeMl": size_ml(size.get_text()) if size else None,
            "stock": stock,
        })
    return out


class Wake:
    def __init__(self, s):
        self.s = s
        self.ok = 0
        self.failed = 0
        self.last = 0.0

    def search(self, term: str, attempts: int = 3) -> list | None:
        for attempt in range(attempts):
            wait = DELAY - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                r = self.s.post(WAKE_SEARCH, data={"productSearch": term}, timeout=TIMEOUT)
                r.raise_for_status()
                self.ok += 1
                return parse_results(r.text)
            except requests.RequestException as e:
                log(f"  retry {attempt + 1} for {term!r}: {e}")
                time.sleep(5 * (attempt + 1))
        self.failed += 1
        return None


def scrape_inventory(s, codes: list, limit: int | None) -> dict:
    wake = Wake(s)
    found = {}  # code -> parsed product
    if limit is None:
        for term in SWEEP_TERMS:
            res = wake.search(term, attempts=1)
            if res is None:
                continue
            for p in res:
                found[p["code"]] = p
            log(f"sweep {term!r}: {len(res)} products (total {len(found)})")
    todo = [c for c in codes if c not in found]
    if limit is not None:
        todo = todo[:limit]
    log(f"per-code searches: {len(todo)}")
    for i, code in enumerate(todo, 1):
        res = wake.search(code)
        for p in res or []:
            found[p["code"]] = p
        if i % 200 == 0:
            log(f"  {i}/{len(todo)}  ok={wake.ok} failed={wake.failed}")
    return {"products": found, "ok": wake.ok, "failed": wake.failed, "attempted": len(todo)}


# ---------------------------------------------------------------- build
def title_case(name: str) -> str:
    t = name.title()
    return re.sub(r"'S\b", "'s", t)


def build(catalog: dict, stores: list, inv: dict) -> dict:
    overrides = {}
    if os.path.exists(OVERRIDES):
        with open(OVERRIDES) as f:
            overrides = {k.zfill(5): v for k, v in json.load(f).items()}

    store_ids = {s["id"] for s in stores}
    per_store = {sid: [] for sid in store_ids}
    products = {}
    unmapped = set()

    for code, p in inv["products"].items():
        in_stock = {}
        for addr, qty in p["stock"].items():
            sid = ADDRESS_TO_ID.get(addr)
            if sid is None or sid not in store_ids:
                unmapped.add(addr)
                continue
            if qty > 0:
                in_stock[sid] = qty
        if not in_stock:
            continue
        c = catalog.get(code, {})
        name = c.get("name") or title_case(p["name"])
        products[code] = {
            "name": name,
            "type": overrides.get(code) or classify(name),
            "sizeMl": c.get("sizeMl") or p["sizeMl"],
            "proof": c.get("proof"),
            "price": p["price"] if p["price"] is not None else c.get("price"),
        }
        for sid, qty in in_stock.items():
            per_store[sid].append([code, qty])

    return {"products": products, "per_store": per_store, "unmapped": sorted(unmapped)}


def write_all(stores, built, inv, catalog_size):
    tmp = tempfile.mkdtemp(prefix="abcspin-")
    os.makedirs(os.path.join(tmp, "inventory"))

    def dump(rel, obj):
        with open(os.path.join(tmp, rel), "w") as f:
            json.dump(obj, f, separators=(",", ":"), ensure_ascii=False)

    dump("stores.json", stores)
    dump("products.json", built["products"])
    for sid, rows in built["per_store"].items():
        dump(f"inventory/{sid}.json", sorted(rows))
    other = sorted({p["name"] for p in built["products"].values() if p["type"] == "Other"})
    with open(os.path.join(tmp, "unclassified.txt"), "w") as f:
        f.write("\n".join(other) + "\n")
    types = {}
    for p in built["products"].values():
        types[p["type"]] = types.get(p["type"], 0) + 1
    dump("meta.json", {
        "updated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "county": "Wake",
        "catalogProducts": catalog_size,
        "productsInStock": len(built["products"]),
        "stores": len(stores),
        "requests": {"ok": inv["ok"], "failed": inv["failed"]},
        "types": types,
        "unmappedAddresses": built["unmapped"],
    })

    # Swap in: keep zips.json and anything else not produced here.
    shutil.rmtree(os.path.join(DATA, "inventory"), ignore_errors=True)
    os.makedirs(DATA, exist_ok=True)
    for name in os.listdir(tmp):
        src, dst = os.path.join(tmp, name), os.path.join(DATA, name)
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.move(src, dst)
    shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="test run: skip sweeps, search only this many codes")
    args = ap.parse_args()

    s = session()
    catalog = fetch_catalog(s)
    stores = fetch_stores(s)
    if len(catalog) < 1000 or len(stores) < 20:
        sys.exit(f"Refusing to continue: catalog={len(catalog)} stores={len(stores)} looks wrong")

    inv = scrape_inventory(s, sorted(catalog), args.limit)
    built = build(catalog, stores, inv)
    log(f"in stock somewhere: {len(built['products'])} products; failed requests: {inv['failed']}")
    if built["unmapped"]:
        log("WARNING unmapped store addresses:", built["unmapped"])

    total = inv["ok"] + inv["failed"]
    if total and inv["failed"] / total > 0.10:
        sys.exit(f"Refusing to publish: {inv['failed']} of {total} requests failed")
    if args.limit is None and len(built["products"]) < 500:
        sys.exit(f"Refusing to publish: only {len(built['products'])} products in stock")

    write_all(stores, built, inv, len(catalog))
    log("done")


if __name__ == "__main__":
    main()
