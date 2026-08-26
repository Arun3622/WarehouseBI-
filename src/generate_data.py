"""
Operational Extract Generator
=============================
Mimics exports from an OLTP order-management system:
  sales_extract.csv  (transaction line items, 2 years)
  customers_extract.csv
  products_extract.csv
These are the raw sources the ETL will model into a star schema.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

random.seed(33)
np.random.seed(33)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW = BASE_DIR / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

N_CUSTOMERS = 2000
N_PRODUCTS = 120
N_LINE_ITEMS = 55000

REGIONS = ["North America", "Europe", "APAC", "LATAM", "MEA"]
REGION_W = [0.38, 0.27, 0.20, 0.09, 0.06]
SEGMENTS = ["Consumer", "Corporate", "Small Business"]
CATEGORIES = {
    "Technology": (90, 2400), "Office Supplies": (5, 180),
    "Furniture": (45, 1300), "Apparel": (12, 260), "Groceries": (3, 85),
}
SUBCATEGORY_SUFFIX = ["Standard", "Premium", "Eco", "Pro", "Lite", "Max"]

FIRST = ["James","Mary","Robert","Patricia","Wei","Aisha","Diego","Fatima","Yuki","Lars",
         "Nadia","Carlos","Ananya","Omar","Elena","Tom","Grace","Ravi","Mei","Lucas"]
LAST = ["Smith","Kumar","Chen","Garcia","Nguyen","Okafor","Silva","Kim","Rossi","Novak",
        "Hassan","Tanaka","Miller","Dubois","Patel","Brown"]


def build_customers():
    rows = []
    for i in range(1, N_CUSTOMERS + 1):
        region = np.random.choice(REGIONS, p=REGION_W)
        rows.append({
            "customer_id": f"CU{i:05d}",
            "name": f"{random.choice(FIRST)} {random.choice(LAST)}",
            "segment": random.choices(SEGMENTS, weights=[55, 25, 20])[0],
            "region": region,
            "country": {"North America": random.choice(["USA", "Canada", "Mexico"]),
                        "Europe": random.choice(["UK", "Germany", "France"]),
                        "APAC": random.choice(["India", "Japan", "Australia"]),
                        "LATAM": random.choice(["Brazil", "Argentina"]),
                        "MEA": random.choice(["UAE", "South Africa"])}[region],
            "signup_date": (datetime(2022, 1, 1) +
                            timedelta(days=random.randint(0, 660))).strftime("%Y-%m-%d"),
        })
    return rows


def build_products():
    rows, i = [], 1
    cat_names = list(CATEGORIES.keys())
    for cat in cat_names:
        lo, hi = CATEGORIES[cat]
        for _ in range(N_PRODUCTS // len(cat_names)):
            price = round(random.uniform(lo, hi), 2)
            rows.append({
                "product_id": f"PR{i:05d}",
                "name": f"{cat[:-1] if cat.endswith('s') else cat} {random.choice(SUBCATEGORY_SUFFIX)} #{i:03d}",
                "category": cat,
                "unit_cost": round(price * random.uniform(0.4, 0.75), 2),
                "list_price": price,
            })
            i += 1
    return rows


def build_sales(customers, products):
    start = datetime(2024, 1, 1)
    days = 730
    cust_w = np.random.pareto(1.4, N_CUSTOMERS)          # power-law customer value
    cust_w /= cust_w.sum()
    cust_ids = np.random.choice([c["customer_id"] for c in customers],
                                size=N_LINE_ITEMS * 3, p=cust_w)
    prod_ids = [p["product_id"] for p in products]
    pmap = {p["product_id"]: p for p in products}
    rows = []
    # seasonal uplift: Nov-Dec holiday bump
    for n in range(N_LINE_ITEMS):
        d = start + timedelta(days=int(np.random.choice(days)))
        month_factor = 1.7 if d.month == 11 or d.month == 12 else \
                       1.15 if d.month in (6, 7) else 1.0
        if random.random() > month_factor / 1.7:
            continue
        cid = cust_ids[n % len(cust_ids)]
        pid = pmap[random.choice(prod_ids)]
        qty = int(np.random.choice([1, 1, 2, 2, 3, 4, 5], p=[.34,.16,.22,.10,.10,.05,.03]))
        discount = random.choice([0, 0, 0, .05, .10, .15, .20])
        unit_price = round(pid["list_price"] * (1 - discount), 2)
        rows.append({
            "order_id": f"SO-{d.year}{d.month:02d}-{n:07d}",
            "line_id": n,
            "order_date": d.strftime("%Y-%m-%d"),
            "ship_date": (d + timedelta(days=random.randint(1, 9))).strftime("%Y-%m-%d"),
            "customer_id": cid,
            "product_id": pid["product_id"],
            "quantity": qty,
            "unit_price": unit_price,
            "discount_pct": int(discount * 100),
            "sales_amount": round(unit_price * qty, 2),
            "channel": random.choices(["online", "retail_store", "partner"],
                                      weights=[62, 28, 10])[0],
        })
    rows.sort(key=lambda r: r["order_date"])
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main():
    print("[generate] building OLTP-style extracts...")
    customers = build_customers()
    products = build_products()
    sales = build_sales(customers, products)
    write_csv(RAW / "customers_extract.csv", customers)
    write_csv(RAW / "products_extract.csv", products)
    write_csv(RAW / "sales_extract.csv", sales)
    print(f"[done] customers={len(customers)}, products={len(products)}, "
          f"line_items={len(sales):,}")


if __name__ == "__main__":
    main()
