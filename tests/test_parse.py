"""Parser tests against markup captured from the live sites on 2026-10-04.

Run: python -m pytest tests   (or: python tests/test_parse.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))
from classify import classify  # noqa: E402
from scrape import build, parse_catalog_csv, parse_results  # noqa: E402
from stores import ADDRESS_TO_ID, clean_store  # noqa: E402

WAKE_HTML = """
<div id="productSearchResults"><h2>Product Search Results</h2><div class="product-row">
  <div class="wake-product">
    <h4>MAKER'S MARK</h4>
    <p><small>PLU: 24275</small></p>
    <p><span class="price">29.95 USD</span> | <span class="size">.750L</span></p>
    <div class="inventory-collapse"><ul class="">
      <li><span class="address">209 S Salisbury St<br />Raleigh, NC 27601</span><span class="quantity">26 in stock</span></li>
      <li><span class="address">4501 Vineyrd Pine Ln.<br />Rolesville, NC 27571</span><span class="quantity">3 in stock</span></li>
      <li><span class="address">999 Nowhere Rd.<br />Raleigh, NC 27601</span><span class="quantity">1 in stock</span></li>
    </ul></div>
  </div>
  <div class="wake-product">
    <h4>MAKER'S MARK CELLAR AGED 2025</h4>
    <p><small>PLU: 17712</small></p>
    <p><span class="price">174.95 USD</span> | <span class="size">.750L</span></p>
  </div>
</div></div>
"""

CSV = (
    '"NC Code","Supplier","Brand Name","Age","Proof","Bottle Size","Retail Bottle Price","Mixed Beverage Price",\r\n'
    '00124,"WhistlePig","WhistlePig 15Y","015Y","92",".75L","$199.95","$203.70",\r\n'
    '24275,"Beam Suntory","Maker\'s Mark","0Y","90",".75L","$29.95","$33.70",\r\n'
    '17158,"Beam Suntory","Maker\'s Mark Cellar Aged 2026","0Y","112","700ML","$174.95","$178.45",\r\n'
)

LOCATOR_ROW = {"id": 2632, "store": "ABC Store 28", "address": "4261 The Circle at North Hills Road",
               "city": "Raleigh", "zip": "", "lat": "35.835640", "lng": "-78.642800",
               "phone": "(919) 000-0000", "hours": "<p>Mon 10:00 AM - 7:00 PM<br />\nSun Closed</p>\n"}


def test_parse_results():
    res = parse_results(WAKE_HTML)
    assert [p["code"] for p in res] == ["24275", "17712"]
    mm = res[0]
    assert mm["price"] == 29.95 and mm["sizeMl"] == 750
    assert mm["stock"]["209 s salisbury st"] == 26
    assert mm["stock"]["4501 vineyrd pine ln"] == 3
    assert res[1]["stock"] == {}


def test_catalog():
    cat = parse_catalog_csv(CSV)
    assert cat["00124"]["proof"] == 92 and cat["00124"]["sizeMl"] == 750
    assert cat["17158"]["sizeMl"] == 700 and cat["17158"]["price"] == 174.95


def test_store_clean():
    s = clean_store(LOCATOR_ROW)
    assert s["zip"] == "27609" and s["lat"] == 35.83564
    assert s["hours"] == "Mon 10:00 AM - 7:00 PM\nSun Closed"


def test_build_joins_and_flags_unmapped():
    cat = parse_catalog_csv(CSV)
    inv = {"products": {p["code"]: p for p in parse_results(WAKE_HTML)}, "ok": 1, "failed": 0}
    stores = [{"id": 3083}, {"id": 198}]
    b = build(cat, stores, inv)
    assert set(b["products"]) == {"24275"}  # cellar aged has no stock
    assert b["products"]["24275"] == {"name": "Maker's Mark", "type": "Whiskey", "sizeMl": 750, "proof": 90.0, "price": 29.95}
    assert b["per_store"][3083] == [["24275", 26]] and b["per_store"][198] == [["24275", 3]]
    assert b["unmapped"] == ["999 nowhere rd"]


def test_all_27_stores_mapped():
    assert len(set(ADDRESS_TO_ID.values())) == 27


def test_real_page_maps_every_store():
    with open(os.path.join(os.path.dirname(__file__), "fixtures", "wake_24275.html")) as f:
        res = parse_results(f.read())
    stock = res[0]["stock"]
    assert len(stock) == 27 and stock["7200 sandy fork rd"] == 566
    assert {ADDRESS_TO_ID[a] for a in stock} == set(ADDRESS_TO_ID.values())


def test_classify():
    cases = {
        "Tito's Handmade Vodka": "Vodka", "Maker's Mark": "Whiskey", "Hendrick's Gin": "Gin",
        "Bacardi Superior": "Rum", "Casamigos Blanco": "Tequila", "Hennessy VS": "Brandy",
        "Baileys Irish Cream": "Liqueur", "Fireball Cinnamon Whisky": "Whiskey",
        "Buffalo Trace Bourbon Cream": "Liqueur", "Kahlúa": "Liqueur", "WhistlePig 15Y": "Whiskey",
    }
    for name, want in cases.items():
        assert classify(name) == want, (name, classify(name), want)


if __name__ == "__main__":
    for k, f in list(globals().items()):
        if k.startswith("test_"):
            f()
            print("ok", k)
