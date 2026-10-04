# ABC Spin

A wheel-of-fortune liquor picker for Wake County, NC ABC stores. Enter a zip code, pick a store, set a price range, bottle size and spirit types, and spin. Only bottles in stock at that store go on the wheel.

## How the data works

A GitHub Actions job runs every morning (`.github/workflows/scrape.yml`):

1. **Catalog**: exports the statewide price list from the [NC ABC Commission](https://abc2.nc.gov/Pricing/PriceList) for proof, size and supplier (about 3,300 products, one request).
2. **Stores**: reads Wake County ABC's store locator feed for ids, coordinates, phone and hours.
3. **Stock**: queries the [Wake County ABC inventory search](https://wakeabc.com/search-our-inventory/), first with a few category keywords, then once per NC code those missed, at about one request per second. A full run takes roughly an hour.
4. Writes `data/`, commits it, and redeploys the site to GitHub Pages.

If a run looks unhealthy (too many failed requests, too few products), the job stops without touching `data/`, so the site keeps the previous day's inventory.

### Data files

| File | Contents |
|---|---|
| `data/meta.json` | Run time, counts, failed requests, store addresses that didn't map |
| `data/stores.json` | Stores with coordinates, phone and hours |
| `data/products.json` | `{code: {name, type, sizeMl, proof, price}}` for products in stock somewhere |
| `data/inventory/<storeId>.json` | `[[code, qty], ...]` |
| `data/zips.json` | NC zip code centers from the Census gazetteer (built once) |
| `data/unclassified.txt` | Products typed "Other", for tuning the classifier |

## Maintenance

- **Spirit types** come from keywords and brand names in `scraper/classify.py`, since neither source has a category field. To fix a single product, add `"NC code": "Type"` to `scraper/overrides.json`.
- **Store addresses**: Wake's inventory search names stores by street address. `scraper/stores.py` maps each to a store-locator id. If Wake opens or moves a store, its address shows up under `unmappedAddresses` in `data/meta.json`; add it to `ADDRESS_TO_ID`. Five mappings are marked *(inferred)* because the two Wake sources list slightly different addresses.
- **Test run**: Actions → Daily inventory scrape → Run workflow, with a `limit` (for example 50) to search only that many product codes.
- **Tests**: `python tests/test_parse.py` runs against markup captured from the live sites.

## Local preview

```
python -m http.server
```
then open http://localhost:8000. The page needs the `data/` files from at least one scrape.

Not affiliated with Wake County ABC or the NC ABC Commission.
