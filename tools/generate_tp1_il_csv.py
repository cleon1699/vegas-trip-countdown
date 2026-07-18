import csv
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pdfplumber


INVOICE_PDF = Path(r"C:\Users\cleon\Downloads\SI_10074740.pdf")
OUTPUT_CSV = Path(r"C:\CodexWorkspaces\New project\output\tp1_il_10074740_v2_direct.csv")
STATE_UPLOAD_CSV = Path(
    r"C:\CodexWorkspaces\New project\output\tp1_il_10074740_v2_state_schedule_upload.csv"
)
REPORT_TXT = Path(r"C:\CodexWorkspaces\New project\output\tp1_il_10074740_v2_report.txt")


CSV_LIMITS = {
    0: 2,
    1: 10,
    2: 7,
    3: 30,
    4: 25,
    5: 50,
    6: 35,
    7: 30,
    8: 2,
    9: 2,
    10: 9,
    11: 9,
    12: 7,
    13: 30,
    14: 5,
    15: 4,
    16: 13,
    17: 10,
    18: 20,
    19: 3,
    20: 50,
    21: 50,
    22: 9,
    23: 50,
    24: 13,
    25: 3,
    26: 13,
    27: 13,
    28: 13,
}

UOM_MAP = {
    "BX": "BOX",
    "BOX": "BOX",
    "PC": "ECH",
    "PCS": "ECH",
    "JAR": "JAR",
    "EA": "ECH",
    "EACH": "ECH",
}

BRAND_PREFIXES = [
    "Backwoods",
    "Celltekk",
    "Foger",
    "Mr Fog",
    "Geek Bar",
    "Geek THC",
    "Half Bak'd",
    "Road Trip",
    "Flying Horse",
    "Double Stacked Bitez",
    "Chapo",
    "Mellow Fellow",
    "Faded",
    "Muha Meds",
    "Cereal Labs",
    "Yocan",
    "Hard Steel",
    "Vip Royal",
    "VIP Royal",
    "Pink Pussycat",
    "Rhino",
    "Swag",
    "Red Mamba",
    "Addall",
    "Visine",
    "Jewelry Scale",
    "Chapstick",
    "Smoking Tray",
    "IDGAF",
    "Eagle",
    "Special Blue",
    "Jamaican",
    "Skeleton",
    "Crushers",
    "Stardust",
    "Butt Bucket",
    "Torch",
]


def clean_text(value: str, limit: int | None = None) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace(",", "")
    value = "".join(ch for ch in value if ord(ch) < 128)
    if limit is not None and len(value) > limit:
        return value[:limit].rstrip()
    return value


def parse_money(value: str) -> str:
    negative = value.startswith("(") and value.endswith(")")
    value = value.strip("()").replace(",", "")
    try:
        number = Decimal(value)
    except InvalidOperation:
        return ""
    if negative:
        number = -number
    return f"{number:.2f}"


def group_words_by_line(words):
    lines = []
    for word in sorted(words, key=lambda item: (item["top"], item["x0"])):
        if word["top"] < 50 or word["top"] > 735:
            continue
        for line in lines:
            if abs(line[0]["top"] - word["top"]) < 3:
                line.append(word)
                break
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: item["x0"]) for line in lines]


def text_in_band(line, low: float, high: float) -> list[str]:
    return [word["text"] for word in line if low <= word["x0"] < high]


def first_text_in_band(line, low: float, high: float) -> str:
    values = text_in_band(line, low, high)
    return values[0] if values else ""


def first_money_in_band(line, low: float, high: float) -> str:
    for value in text_in_band(line, low, high):
        if re.fullmatch(r"\(?[0-9][0-9,]*\.[0-9]{2}\)?", value):
            return value
    return ""


def is_item_line(line) -> bool:
    qty = first_text_in_band(line, 116, 135)
    uom = first_text_in_band(line, 133, 158).upper()
    price = first_money_in_band(line, 445, 500)
    ext = first_money_in_band(line, 540, 590)
    return bool(qty and uom and price and ext and re.search(r"\d", qty))


def is_discount_line(line) -> bool:
    qty = first_text_in_band(line, 116, 135)
    desc = " ".join(text_in_band(line, 158, 445)).upper()
    price = first_money_in_band(line, 445, 500)
    ext = first_money_in_band(line, 540, 590)
    return bool(qty and "DISCOUNT" in desc and price and ext)


def extract_items() -> list[dict]:
    items = []
    with pdfplumber.open(INVOICE_PDF) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            for line in group_words_by_line(page.extract_words()):
                line_text = " ".join(word["text"] for word in line)
                if "UPC/Barcode" in line_text or "UNIT" in line_text or "PRICE" in line_text:
                    continue
                if line_text.startswith(("07/08/2026", "TRANSACTION NO.", "TOTAL ", "OTP TAX", "FREIGHT")):
                    continue

                if is_item_line(line):
                    upc = " ".join(text_in_band(line, 0, 110))
                    qty = first_text_in_band(line, 116, 135)
                    uom = first_text_in_band(line, 133, 158)
                    desc = " ".join(text_in_band(line, 158, 445))
                    price = first_money_in_band(line, 445, 500)
                    extended = first_money_in_band(line, 540, 590)
                    items.append(
                        {
                            "page": page_index,
                            "upc": clean_text(upc, 20),
                            "qty": qty.strip("()"),
                            "uom": uom.upper(),
                            "desc": clean_text(desc),
                            "unit_price": parse_money(price),
                            "extended": parse_money(extended),
                        }
                    )
                elif is_discount_line(line):
                    qty = first_text_in_band(line, 116, 135)
                    desc = " ".join(text_in_band(line, 158, 445))
                    price = first_money_in_band(line, 445, 500)
                    extended = first_money_in_band(line, 540, 590)
                    items.append(
                        {
                            "page": page_index,
                            "upc": "",
                            "qty": qty.strip("()"),
                            "uom": "OTH",
                            "desc": clean_text(desc),
                            "unit_price": parse_money(extended) or parse_money(price),
                            "extended": parse_money(extended),
                        }
                    )
                elif items and line and 150 <= line[0]["x0"] < 200:
                    continuation = " ".join(word["text"] for word in line if word["x0"] < 445)
                    items[-1]["desc"] = clean_text(f"{items[-1]['desc']} {continuation}")
    return items


def classify(description: str) -> tuple[str, str]:
    upper = description.upper()
    if any(term in upper for term in ["VAPE", "PUFF", "DISPOSABLE POD", "E-CIG", "ECIG"]):
        return "Vapor Products", "ECIG"
    return "Other", "OTP"


def classify_state_upload(description: str) -> tuple[str, str]:
    upper = description.upper()
    if any(term in upper for term in ["VAPE", "PUFF", "DISPOSABLE POD", "E-CIG", "ECIG"]):
        return "Vapor Product", "E-cigarettes"
    return "Other", "Tobacco Products excluding Moist Snuff and E-cigarettes"


def infer_brand(description: str) -> str:
    lower = description.lower()
    for prefix in BRAND_PREFIXES:
        if lower.startswith(prefix.lower()):
            return clean_text(prefix, 50)
    words = clean_text(description).split()
    return clean_text(" ".join(words[:2]), 50) if words else ""


def infer_unit(description: str) -> str:
    matches = re.findall(r"(\d+)\s*[Cc][Tt]\b", description)
    return matches[-1] if matches else "1"


def to_csv_row(item: dict) -> list[str]:
    fed_desc, state_desc = classify(item["desc"])
    uom = UOM_MAP.get(item["uom"].upper(), "OTH")
    brand = infer_brand(item["desc"])
    row = [
        "1B",
        "1/16/2026",
        "Invoice",
        "10074740",
        "Distributor",
        "Hoosier Wholesale Distributors",
        "",
        "",
        "",
        "US",
        "",
        "",
        "",
        fed_desc,
        state_desc,
        "N/A",
        "",
        "IL",
        item["upc"],
        uom,
        item["desc"],
        brand,
        "",
        brand,
        infer_unit(item["desc"]),
        uom,
        "",
        item["unit_price"],
        item["qty"],
    ]
    return [clean_text(value, CSV_LIMITS[index]) for index, value in enumerate(row)]


def display_uom(code: str) -> str:
    return {
        "BOX": "Box",
        "ECH": "Eaches",
        "JAR": "Jar",
        "OTH": "Other",
    }.get(code, "Other")


def to_state_upload_row(item: dict) -> list[str]:
    fed_desc, state_desc = classify_state_upload(item["desc"])
    uom_code = UOM_MAP.get(item["uom"].upper(), "OTH")
    uom = display_uom(uom_code)
    brand = infer_brand(item["desc"])
    value = item["unit_price"]
    quantity = item["qty"]
    try:
        extended = f"{Decimal(value) * Decimal(quantity):.2f}"
    except InvalidOperation:
        extended = value
    return [
        clean_text(fed_desc),
        clean_text(state_desc),
        "Not Applicable",
        value,
        "Illinois",
        clean_text(item["upc"], 20),
        uom,
        clean_text(item["desc"], 50),
        clean_text(brand, 50),
        "",
        clean_text(brand, 50),
        f"{Decimal(infer_unit(item['desc'])):.2f}",
        uom,
        "0.00",
        value,
        quantity,
        "0.00",
        extended,
        "Distributor",
        "Hoosier Wholesale Distributors",
        "Invoice",
        "10074740",
        "",
        "",
        "ILLINOIS",
        "USA",
        "",
        "",
        "",
        "16-Jan-2026",
    ]


def validate(rows: list[list[str]]) -> list[str]:
    errors = []
    for line_number, row in enumerate(rows, start=1):
        if len(row) != 29:
            errors.append(f"Line {line_number}: expected 29 columns, found {len(row)}")
        for index, value in enumerate(row):
            limit = CSV_LIMITS[index]
            if len(value) > limit:
                errors.append(
                    f"Line {line_number}, column {index + 1}: length {len(value)} exceeds {limit}"
                )
            if "," in value:
                errors.append(f"Line {line_number}, column {index + 1}: contains comma")
    return errors


def validate_state_upload(rows: list[list[str]]) -> list[str]:
    errors = []
    for line_number, row in enumerate(rows, start=1):
        if len(row) != 30:
            errors.append(f"State upload line {line_number}: expected 30 columns, found {len(row)}")
        for index in [0, 1, 3, 5, 14]:
            if not row[index]:
                errors.append(f"State upload line {line_number}: required column {index + 1} is blank")
    return errors


def main() -> None:
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    items = extract_items()
    rows = [to_csv_row(item) for item in items]
    state_items = [item for item in items if item["upc"] and item["desc"].lower() != "discount"]
    state_rows = [to_state_upload_row(item) for item in state_items]
    errors = validate(rows)
    errors.extend(validate_state_upload(state_rows))
    if errors:
        raise SystemExit("\n".join(errors))

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(rows)
    with STATE_UPLOAD_CSV.open("w", newline="", encoding="utf-8") as output:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerows(state_rows)

    total_extended = sum(Decimal(item["extended"]) for item in items if item["extended"])
    total_values = sum(Decimal(item["unit_price"]) * Decimal(item["qty"]) for item in items if item["unit_price"])
    excluded_for_state = len(items) - len(state_items)
    report = [
        f"Generated CSV: {OUTPUT_CSV}",
        f"Generated state schedule upload CSV: {STATE_UPLOAD_CSV}",
        f"Input invoice: {INVOICE_PDF}",
        f"Rows generated: {len(rows)}",
        f"State schedule upload rows generated: {len(state_rows)}",
        f"Rows excluded from state schedule upload for blank UPC or discount: {excluded_for_state}",
        f"Sum of invoice extended prices parsed: {total_extended:.2f}",
        f"Sum of CSV value x quantity: {total_values:.2f}",
        "Validation: direct CSV rows have 29 columns; state upload rows have 30 columns; required state upload Federal/State/Price/UPC/Value fields are populated.",
        "",
        "Rows by page:",
    ]
    by_page = {}
    for item in items:
        by_page[item["page"]] = by_page.get(item["page"], 0) + 1
    report.extend(f"  Page {page}: {count}" for page, count in sorted(by_page.items()))
    REPORT_TXT.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main()
