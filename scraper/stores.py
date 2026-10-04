"""Wake County store metadata.

Wake's inventory search names stores only by street address, while the
store locator feed has ids, coordinates and hours. ADDRESS_TO_ID joins
the two. Keys are the inventory address's first line, normalized by
norm_addr(). Rows marked (inferred) don't match the locator address exactly
and were matched by street/town; confirm them before relying on them.
"""
import re

ADDRESS_TO_ID = {
    "209 s salisbury st": 3083,          # ABC Store 27
    "1222 new bern ave": 187,            # ABC Store 9
    "420 woodburn rd": 193,              # ABC Store 8
    "2109-106 avent ferry rd": 189,      # ABC Store 4
    "1601-61 cross link rd": 188,        # ABC Store 19
    "2645 appliance ct": 192,            # ABC Store 10 (inferred: locator says 2649)
    "3320 olympia dr": 190,              # ABC Store 11
    "4215 the circle at north hills rd": 2632,  # ABC Store 28 (inferred: locator says 4261)
    "200 new rand road": 181,            # ABC Store 18
    "7200 sandy fork rd": 197,           # ABC Store 1 (inferred: locator says 7112 Sandy Forks)
    "6809 davis circle": 194,            # ABC Store 6
    "6301 town center dr": 191,          # ABC Store 17
    "665 cary towne blvd": 180,          # ABC Store 15
    "6494 tryon rd": 179,                # ABC Store 2
    "7336 creedmoor rd": 195,            # ABC Store 20
    "704 money ct": 184,                 # ABC Store 21
    "3615 sw cary parkway": 178,         # ABC Store 7
    "1415 e williams st": 176,           # ABC Store 22 (inferred: locator says 1415 Hwy 55 S)
    "7911 acc blvd": 196,                # ABC Store 23
    "1505 banyon pl": 1123,              # ABC Store 26 (inferred: only Wendell store)
    "4501 vineyrd pine ln": 198,         # ABC Store 25 (Wake's own spelling)
    "4501 vineyard pine ln": 198,
    "4009 davis dr": 185,                # ABC Store 3
    "11360 capital blvd": 199,           # ABC Store 14
    "1793 west williams st": 177,        # ABC Store 12
    "1940 cinema dr": 183,               # ABC Store 13
    "100 village walk dr": 182,          # ABC Store 24
    "1420 n ardendell dr": 200,          # ABC Store 5
}

# Fixes for bad fields in the locator feed.
ZIP_FIXES = {2632: "27609", 1123: "27591"}

EXCLUDE_IDS = {186}  # ABC Warehouse, not a retail store

LOCATOR_URL = (
    "https://wakeabc.com/wp-admin/admin-ajax.php?action=store_search"
    "&lat=35.7796&lng=-78.6382&max_results=100&search_radius=500&autoload=1"
)


def norm_addr(line: str) -> str:
    s = line.lower().replace(".", " ").replace(",", " ")
    return re.sub(r"\s+", " ", s).strip()


def clean_store(raw: dict) -> dict:
    sid = int(raw["id"])
    zip_ = ZIP_FIXES.get(sid, str(raw.get("zip") or "").strip())
    hours = re.sub(r"<br\s*/?>", "\n", raw.get("hours") or "")
    hours = re.sub(r"<[^>]+>", "", hours)
    hours = "\n".join(l.strip() for l in hours.splitlines() if l.strip())
    return {
        "id": sid,
        "name": raw.get("store", "").strip(),
        "address": raw.get("address", "").strip(),
        "city": raw.get("city", "").strip(),
        "zip": zip_,
        "lat": float(raw["lat"]),
        "lng": float(raw["lng"]),
        "phone": (raw.get("phone") or "").strip(),
        "hours": hours,
    }
