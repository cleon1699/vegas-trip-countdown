import csv
import html
import json
import re
import sys
import time
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urljoin
from urllib.request import Request, urlopen

import pdfplumber


BASE_URL = "https://hoosierwholesale.com"
INVOICE_PDF = Path(r"C:\Users\cleon\Downloads\SI_10074740.pdf")
OUTPUT_CSV = Path(r"C:\CodexWorkspaces\New project\output\SI_10074740_categories.csv")
CACHE_JSON = Path(r"C:\CodexWorkspaces\New project\output\hoosier_category_cache.json")

PRICE_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$|^\d+\.\d{2}$")
UPC_RE = re.compile(r"^\d{8,14}$")


@dataclass
class InvoiceItem:
    invoice_no: str
    invoice_date: str
    upc_barcode: str
    qty: str
    unit: str
    description: str
    unit_price: str
    extended_price: str


@dataclass
class LookupResult:
    category: str = ""
    matched_product_name: str = ""
    matched_url: str = ""
    match_status: str = "not_found"
    notes: str = ""


def clean_space(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_for_match(value: str) -> str:
    value = html.unescape(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return clean_space(value)


def product_base(description: str) -> str:
    base = re.sub(r"\s*\([^)]*$", "", description)
    base = re.sub(r"\s*\([^)]*\)", "", base)
    return clean_space(base)


def line_groups(page) -> List[List[dict]]:
    words = page.extract_words(x_tolerance=1, y_tolerance=3, keep_blank_chars=False)
    lines: List[List[dict]] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        if not lines or abs(lines[-1][0]["top"] - word["top"]) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    return lines


def text_in(words: Iterable[dict], x_min: float, x_max: float) -> str:
    return clean_space(" ".join(w["text"] for w in words if x_min <= w["x0"] < x_max))


def extract_invoice_items(pdf_path: Path) -> List[InvoiceItem]:
    items: List[InvoiceItem] = []
    invoice_no = ""
    invoice_date = ""
    previous: Optional[InvoiceItem] = None

    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            for line in line_groups(page):
                whole = clean_space(" ".join(w["text"] for w in line))
                if whole.startswith("DATE "):
                    invoice_date = whole.replace("DATE ", "", 1)
                if whole.startswith("INVOICE NO. "):
                    invoice_no = whole.replace("INVOICE NO. ", "", 1)

                upc = text_in(line, 0, 105)
                qty = text_in(line, 112, 136)
                unit = text_in(line, 136, 158)
                desc = text_in(line, 158, 446)
                unit_price = text_in(line, 446, 486)
                extended_price = text_in(line, 535, 610)

                is_item = bool(qty.isdigit() and unit and desc and PRICE_RE.match(unit_price) and PRICE_RE.match(extended_price))
                if is_item:
                    if upc and not UPC_RE.match(upc):
                        upc = ""
                    previous = InvoiceItem(
                        invoice_no=invoice_no,
                        invoice_date=invoice_date,
                        upc_barcode=upc,
                        qty=qty,
                        unit=unit,
                        description=desc,
                        unit_price=unit_price,
                        extended_price=extended_price,
                    )
                    items.append(previous)
                    continue

                # Wrapped flavor text often appears on its own line under DESCRIPTION after prices.
                continuation = desc or text_in(line, 158, 446)
                if previous and continuation and not qty and not unit_price and not extended_price:
                    skipped = ("UPC/Barcode", "TRANSACTION", "Page ", "OTP TAX", "TOTAL")
                    if not any(whole.startswith(s) for s in skipped):
                        previous.description = clean_space(f"{previous.description} {continuation}")

    return items


def fetch(url: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "KHTML, like Gecko) Chrome/126.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str, timeout: int = 30):
    return json.loads(fetch(url, timeout=timeout))


def product_slug(description: str) -> str:
    slug = html.unescape(description).lower()
    slug = slug.replace("&", " ")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def candidate_queries(item: InvoiceItem) -> List[str]:
    queries: List[str] = []
    queries.append(item.description)
    base = product_base(item.description)
    if base and base != item.description:
        queries.append(base)
    # Try without count/case noise as a last search-page fallback.
    relaxed = re.sub(r"\b\d+\s*(?:ct|pk|pack|puffs?|mg|mah)\b", " ", base, flags=re.I)
    relaxed = clean_space(relaxed)
    if relaxed and relaxed not in queries:
        queries.append(relaxed)
    if item.upc_barcode:
        queries.append(item.upc_barcode)
    return list(dict.fromkeys(queries))


def parse_title(page_html: str) -> str:
    match = re.search(r"<h1[^>]*class=[\"'][^\"']*product_title[^\"']*[\"'][^>]*>(.*?)</h1>", page_html, re.I | re.S)
    if match:
        return clean_space(re.sub(r"<[^>]+>", " ", html.unescape(match.group(1))))
    match = re.search(r"<title>(.*?)</title>", page_html, re.I | re.S)
    if match:
        return clean_space(html.unescape(match.group(1)).replace("- Hoosier Wholesale", ""))
    return ""


def parse_category(page_html: str) -> str:
    posted = re.search(r"<span[^>]*class=[\"'][^\"']*posted_in[^\"']*[\"'][^>]*>(.*?)</span>", page_html, re.I | re.S)
    if posted:
        text = clean_space(re.sub(r"<[^>]+>", " ", html.unescape(posted.group(1))))
        text = re.sub(r"^Categor(?:y|ies):\s*", "", text, flags=re.I)
        if text:
            return text
    category = re.search(r"Category:\s*</span>\s*<a[^>]*>(.*?)</a>", page_html, re.I | re.S)
    if category:
        return clean_space(re.sub(r"<[^>]+>", " ", html.unescape(category.group(1))))
    return ""


def search_product_links(query: str) -> List[Tuple[str, str]]:
    search_url = f"{BASE_URL}/?s={quote_plus(query)}&post_type=product"
    page_html = fetch(search_url)
    pairs = re.findall(
        r"<a[^>]+href=[\"'](https://hoosierwholesale\.com/product/[^\"']+/)[\"'][^>]*>(.*?)</a>",
        page_html,
        flags=re.I | re.S,
    )
    results: List[Tuple[str, str]] = []
    seen = set()
    for url, title_html in pairs:
        title = clean_space(re.sub(r"<[^>]+>", " ", html.unescape(title_html)))
        if not title or url in seen:
            continue
        seen.add(url)
        results.append((title, url))
    return results[:12]


def api_search_products(query: str) -> List[dict]:
    search_url = f"{BASE_URL}/wp-json/wc/store/v1/products?search={quote_plus(query)}&per_page=25"
    data = fetch_json(search_url)
    return data if isinstance(data, list) else []


def product_api_category(product: dict) -> str:
    categories = product.get("categories") or []
    names = [clean_space(html.unescape(category.get("name", ""))) for category in categories if category.get("name")]
    return ", ".join(name for name in names if name)


def fallback_category(item: InvoiceItem) -> LookupResult:
    desc = item.description.lower()
    if "jewelry scale" in desc or "pocket scale" in desc:
        return LookupResult(category="Scales", match_status="review", notes="fallback by invoice description keyword: scale")
    if "grinder" in desc:
        return LookupResult(category="Grinders", match_status="review", notes="fallback by invoice description keyword: grinder")
    if "ashtray" in desc:
        return LookupResult(category="Ashtrays", match_status="review", notes="fallback by invoice description keyword: ashtray")
    if "torch" in desc and "seltzer" not in desc:
        return LookupResult(category="Lighters/Torches", match_status="review", notes="fallback by invoice description keyword: torch")
    if "cartridge" in desc:
        return LookupResult(category="Cartridges", match_status="review", notes="fallback by invoice description keyword: cartridge")
    if "disposable" in desc:
        if "puff" in desc or "pod" in desc or "geek bar" in desc or "foger" in desc or "mr fog" in desc:
            return LookupResult(category="E-Cigs & Disposables", match_status="review", notes="fallback by invoice description keyword: vape disposable")
        return LookupResult(category="Disposables", match_status="review", notes="fallback by invoice description keyword: disposable")
    if "gumm" in desc or "seltzer" in desc:
        return LookupResult(category="Edibles", match_status="review", notes="fallback by invoice description keyword: edible/seltzer")
    return LookupResult(notes="searched: " + " | ".join(candidate_queries(item)))


def score_match(item: InvoiceItem, title: str, query: str) -> float:
    target = normalize_for_match(item.description)
    base = normalize_for_match(product_base(item.description))
    candidate = normalize_for_match(title)
    ratio = max(SequenceMatcher(None, target, candidate).ratio(), SequenceMatcher(None, base, candidate).ratio())
    target_tokens = set(target.split())
    base_tokens = set(base.split())
    candidate_tokens = set(candidate.split())
    overlap = len((base_tokens or target_tokens) & candidate_tokens) / max(1, len(base_tokens or target_tokens))
    if item.upc_barcode and query == item.upc_barcode:
        ratio += 0.1
    return max(ratio, overlap)


def lookup_item(item: InvoiceItem) -> LookupResult:
    api_candidates: List[Tuple[float, dict, str]] = []
    for query in candidate_queries(item):
        try:
            for product in api_search_products(query):
                title = clean_space(html.unescape(product.get("name", "")))
                if title and title.lower() != "login":
                    api_candidates.append((score_match(item, title, query), product, query))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            continue
        if api_candidates and max(c[0] for c in api_candidates) >= 0.92:
            break
        time.sleep(0.15)

    if api_candidates:
        score, product, query = sorted(api_candidates, reverse=True, key=lambda c: c[0])[0]
        title = clean_space(html.unescape(product.get("name", "")))
        category = product_api_category(product)
        url = product.get("permalink") or product.get("link") or ""
        if category and score >= 0.45:
            status = "matched" if score >= 0.86 else "review"
            return LookupResult(category, title, url, status, f"store api query={query}; score={score:.2f}")

    direct_urls = []
    for desc in (item.description, product_base(item.description)):
        slug = product_slug(desc)
        if slug:
            direct_urls.append(f"{BASE_URL}/product/{slug}/")

    checked_urls = set()
    candidates: List[Tuple[float, str, str, str]] = []

    for url in dict.fromkeys(direct_urls):
        try:
            page_html = fetch(url)
            title = parse_title(page_html)
            if title.lower() == "login":
                continue
            category = parse_category(page_html)
            if category:
                score = score_match(item, title, item.description)
                status = "matched" if score >= 0.88 else "review"
                return LookupResult(category, title, url, status, f"direct slug score={score:.2f}")
        except (HTTPError, URLError, TimeoutError):
            pass
        checked_urls.add(url)

    for query in candidate_queries(item):
        try:
            links = search_product_links(query)
        except (HTTPError, URLError, TimeoutError) as exc:
            continue
        for title, url in links:
            if url in checked_urls:
                continue
            checked_urls.add(url)
            candidates.append((score_match(item, title, query), title, url, query))
        if candidates and max(c[0] for c in candidates) >= 0.92:
            break
        time.sleep(0.15)

    if not candidates:
        return fallback_category(item)

    score, title, url, query = sorted(candidates, reverse=True, key=lambda c: c[0])[0]
    try:
            page_html = fetch(url)
            category = parse_category(page_html)
            page_title = parse_title(page_html) or title
            if page_title.lower() == "login":
                fallback = fallback_category(item)
                fallback.matched_product_name = title
                fallback.matched_url = url
                fallback.notes = clean_space(f"{fallback.notes}; product page protected; query={query}; score={score:.2f}")
                return fallback
    except (HTTPError, URLError, TimeoutError) as exc:
        return LookupResult(matched_product_name=title, matched_url=url, match_status="review", notes=f"matched search result but page fetch failed: {exc}")

    if not category:
        return LookupResult(matched_product_name=page_title, matched_url=url, match_status="review", notes=f"no category parsed; query={query}; score={score:.2f}")

    status = "matched" if score >= 0.86 else "review"
    return LookupResult(category, page_title, url, status, f"query={query}; score={score:.2f}")


def load_cache() -> Dict[str, dict]:
    if CACHE_JSON.exists():
        return json.loads(CACHE_JSON.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: Dict[str, dict]) -> None:
    CACHE_JSON.parent.mkdir(parents=True, exist_ok=True)
    CACHE_JSON.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def lookup_all(items: List[InvoiceItem]) -> Dict[str, LookupResult]:
    cache = load_cache()
    results: Dict[str, LookupResult] = {}
    keys = list(dict.fromkeys(product_base(item.description) for item in items))
    for index, key in enumerate(keys, 1):
        if key in cache:
            results[key] = LookupResult(**cache[key])
            continue
        representative = next(item for item in items if product_base(item.description) == key)
        print(f"[{index}/{len(keys)}] {key}", flush=True)
        result = lookup_item(representative)
        results[key] = result
        cache[key] = asdict(result)
        save_cache(cache)
        time.sleep(0.2)
    return results


def write_csv(items: List[InvoiceItem], lookups: Dict[str, LookupResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "invoice_no",
        "invoice_date",
        "upc_barcode",
        "qty",
        "unit",
        "description",
        "unit_price",
        "extended_price",
        "category",
        "matched_product_name",
        "matched_url",
        "match_status",
        "notes",
    ]
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            lookup = lookups.get(product_base(item.description), LookupResult())
            row = asdict(item)
            row.update(asdict(lookup))
            writer.writerow(row)


def main() -> int:
    items = extract_invoice_items(INVOICE_PDF)
    print(f"Extracted {len(items)} invoice line items")
    lookups = lookup_all(items)
    write_csv(items, lookups, OUTPUT_CSV)

    first = items[0] if items else None
    if first:
        first_lookup = lookups.get(product_base(first.description), LookupResult())
        print(f"First item: {first.description} -> {first_lookup.category} ({first_lookup.match_status})")
    status_counts: Dict[str, int] = {}
    for item in items:
        status = lookups.get(product_base(item.description), LookupResult()).match_status
        status_counts[status] = status_counts.get(status, 0) + 1
    print(f"Status counts: {status_counts}")
    print(f"Wrote {OUTPUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
