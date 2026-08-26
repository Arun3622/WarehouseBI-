"""
Sales Data Warehouse ETL + SQL Analytics
========================================
Builds a Kimball-style star schema in SQLite:

    dim_date  ─┐
    dim_customer ├─▶ fact_sales ──▶ analytical SQL (RFM, cohorts, YoY, pareto)
    dim_product ┘

Then runs the warehouse queries that power the dashboard.

Run: python src/pipeline.py
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW = BASE_DIR / "data" / "raw"
OUT = BASE_DIR / "data"
OUT.mkdir(exist_ok=True)
DB_PATH = OUT / "warehouse.db"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("dw")


DDL = """
DROP TABLE IF EXISTS fact_sales; DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_customer; DROP TABLE IF EXISTS dim_product;

CREATE TABLE dim_date (
    date_key     INTEGER PRIMARY KEY,   -- yyyymmdd
    full_date    TEXT NOT NULL,
    year         INTEGER, quarter INTEGER, month INTEGER,
    month_name   TEXT, day_of_week TEXT, is_weekend INTEGER);

CREATE TABLE dim_customer (
    customer_key INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id  TEXT UNIQUE, name TEXT, segment TEXT,
    region TEXT, country TEXT, signup_date TEXT);

CREATE TABLE dim_product (
    product_key  INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id   TEXT UNIQUE, name TEXT, category TEXT,
    unit_cost REAL, list_price REAL);

CREATE TABLE fact_sales (
    sales_key      INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       TEXT, line_id INTEGER,
    date_key       INTEGER REFERENCES dim_date(date_key),
    customer_key   INTEGER REFERENCES dim_customer(customer_key),
    product_key    INTEGER REFERENCES dim_product(product_key),
    quantity       INTEGER, unit_price REAL, discount_pct INTEGER,
    sales_amount   REAL, profit_amount REAL, channel TEXT);
"""


def build_dims(con: sqlite3.Connection):
    customers = pd.read_csv(RAW / "customers_extract.csv")
    products = pd.read_csv(RAW / "products_extract.csv")

    con.executescript(DDL)  # fresh, clean star-schema tables
    customers.to_sql("dim_customer_staging", con, index=False)
    products.to_sql("dim_product_staging", con, index=False)

    con.execute("""INSERT INTO dim_customer (customer_id,name,segment,region,country,signup_date)
                   SELECT customer_id,name,segment,region,country,signup_date
                   FROM dim_customer_staging""")
    con.execute("""INSERT INTO dim_product (product_id,name,category,unit_cost,list_price)
                   SELECT product_id,name,category,unit_cost,list_price
                   FROM dim_product_staging""")

    # dim_date from the sales horizon
    con.execute("""
        WITH RECURSIVE dates(d) AS (
            SELECT date('2024-01-01')
            UNION ALL SELECT date(d, '+1 day') FROM dates WHERE d < date('2025-12-31')
        )
        INSERT INTO dim_date (date_key, full_date, year, quarter, month,
                              month_name, day_of_week, is_weekend)
        SELECT CAST(strftime('%Y%m%d', d) AS INTEGER), d,
               CAST(strftime('%Y', d) AS INTEGER),
               (CAST(strftime('%m', d) AS INTEGER) + 2) / 3,
               CAST(strftime('%m', d) AS INTEGER),
               CASE CAST(strftime('%m', d) AS INTEGER)
                    WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar' WHEN 4 THEN 'Apr'
                    WHEN 5 THEN 'May' WHEN 6 THEN 'Jun' WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug'
                    WHEN 9 THEN 'Sep' WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dec' END,
               CASE CAST(strftime('%w', d) AS INTEGER)
                    WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
                    WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday'
                    WHEN 5 THEN 'Friday' ELSE 'Saturday' END,
               CASE WHEN strftime('%w', d) IN ('0','6') THEN 1 ELSE 0 END
        FROM dates""")
    con.commit()
    for t in ["dim_customer", "dim_product", "dim_date"]:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        log.info(f"LOAD DIM | {t}: {n:,} rows")
    con.execute("DROP TABLE IF EXISTS dim_customer_staging")
    con.execute("DROP TABLE IF EXISTS dim_product_staging")


def load_facts(con: sqlite3.Connection):
    sales = pd.read_csv(RAW / "sales_extract.csv")
    sales["date_key"] = sales["order_date"].str.replace("-", "").astype(int)

    con.executescript("""
        CREATE TEMP TABLE stage_sales AS SELECT 1 WHERE 0;
        DROP TABLE IF EXISTS temp.stage_sales;
        CREATE TEMP TABLE stage_sales (
            order_id TEXT, line_id INTEGER, date_key INTEGER,
            customer_id TEXT, product_id TEXT, quantity INTEGER,
            unit_price REAL, discount_pct INTEGER,
            sales_amount REAL, channel TEXT);
    """)
    sales[["order_id","line_id","date_key","customer_id","product_id",
           "quantity","unit_price","discount_pct","sales_amount","channel"]] \
        .to_sql("stage_sales", con, if_exists="append", index=False)

    con.execute("""
        INSERT INTO fact_sales (order_id, line_id, date_key, customer_key, product_key,
                                quantity, unit_price, discount_pct, sales_amount,
                                profit_amount, channel)
        SELECT s.order_id, s.line_id, s.date_key,
               dc.customer_key, dp.product_key,
               s.quantity, s.unit_price, s.discount_pct, s.sales_amount,
               ROUND((dp.list_price - dp.unit_cost) * s.quantity * (1 - s.discount_pct/100.0), 2),
               s.channel
        FROM stage_sales s
        JOIN dim_customer dc ON dc.customer_id = s.customer_id
        JOIN dim_product  dp ON dp.product_id  = s.product_id""")
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0]
    log.info(f"LOAD FACT| fact_sales: {n:,} rows")


def run_analytics(con: sqlite3.Connection) -> dict:
    agg = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    q = lambda sql: pd.read_sql(sql, con).to_dict("records")

    agg["kpis"] = q("""
        SELECT COUNT(*) total_lines, COUNT(DISTINCT order_id) orders,
               COUNT(DISTINCT customer_key) customers,
               ROUND(SUM(sales_amount)) revenue, ROUND(SUM(profit_amount)) profit,
               ROUND(AVG(sales_amount),2) avg_line_value
        FROM fact_sales""")[0]

    # monthly trend with YoY growth via window function
    agg["monthly"] = q("""
        WITH m AS (
          SELECT dd.year, dd.month, dd.month_name,
                 SUM(fs.sales_amount) revenue, COUNT(DISTINCT fs.order_id) orders
          FROM fact_sales fs JOIN dim_date dd ON dd.date_key = fs.date_key
          GROUP BY dd.year, dd.month)
        SELECT year, month, month_name, ROUND(revenue) revenue, orders,
               ROUND(100.0*(revenue - LAG(revenue) OVER (ORDER BY year, month))
                     / NULLIF(LAG(revenue) OVER (ORDER BY year, month),0),1) mom_growth_pct
        FROM m ORDER BY year, month""")

    # category performance
    agg["category"] = q("""
        SELECT dp.category, ROUND(SUM(fs.sales_amount)) revenue,
               ROUND(SUM(fs.profit_amount)) profit, SUM(fs.quantity) units,
               ROUND(SUM(fs.profit_amount)*100.0/SUM(fs.sales_amount),1) margin_pct
        FROM fact_sales fs JOIN dim_product dp USING(product_key)
        GROUP BY dp.category ORDER BY revenue DESC""")

    # region performance
    agg["region"] = q("""
        SELECT dc.region, ROUND(SUM(fs.sales_amount)) revenue,
               COUNT(DISTINCT fs.customer_key) active_customers
        FROM fact_sales fs JOIN dim_customer dc USING(customer_key)
        GROUP BY dc.region ORDER BY revenue DESC""")

    # RFM segmentation (pure SQL)
    agg["rfm"] = q("""
        WITH rfm AS (
          SELECT customer_key,
                 MAX(date_key) last_purchase,
                 COUNT(DISTINCT order_id) frequency,
                 ROUND(SUM(sales_amount)) monetary
          FROM fact_sales GROUP BY customer_key),
        scored AS (
          SELECT *, NTILE(5) OVER (ORDER BY last_purchase DESC) recency_score,
                    NTILE(5) OVER (ORDER BY frequency) frequency_score,
                    NTILE(5) OVER (ORDER BY monetary) monetary_score
          FROM rfm)
        SELECT CASE
            WHEN frequency_score >= 4 AND monetary_score >= 4 THEN 'Champions'
            WHEN recency_score >= 3 AND frequency_score >= 3 THEN 'Loyal'
            WHEN recency_score >= 4 AND frequency_score <= 2 THEN 'New / Promising'
            WHEN recency_score <= 2 AND monetary_score >= 3 THEN 'At Risk'
            WHEN recency_score <= 2 AND frequency_score <= 2 AND monetary_score <= 2 THEN 'Hibernating'
            ELSE 'Potential Loyalist' END segment,
            COUNT(*) customers,
            ROUND(SUM(monetary)) revenue
        FROM scored GROUP BY segment ORDER BY revenue DESC""")

    # top customers by value
    agg["top_customers"] = q("""
        SELECT dc.name || ' · ' || dc.country customer, dc.segment,
               COUNT(DISTINCT fs.order_id) orders,
               ROUND(SUM(fs.sales_amount)) revenue
        FROM fact_sales fs JOIN dim_customer dc USING(customer_key)
        GROUP BY fs.customer_key ORDER BY revenue DESC LIMIT 10""")

    # quarterly cohort retention (SQL window over cohort grid)
    agg["cohorts"] = q("""
        WITH first_order AS (
          SELECT fs.customer_key,
                 MIN(dd.year*100 + dd.month) cohort
          FROM fact_sales fs JOIN dim_date dd ON dd.date_key=fs.date_key
          GROUP BY fs.customer_key),
        activity AS (
          SELECT fo.customer_key, fo.cohort,
                 (dd.year*100+dd.month - fo.cohort) months_since
          FROM fact_sales fs
          JOIN dim_date dd ON dd.date_key=fs.date_key
          JOIN first_order fo ON fo.customer_key=fs.customer_key),
        cohort_size AS (SELECT cohort, COUNT(*) n FROM first_order GROUP BY cohort),
        retained AS (SELECT cohort, MAX(months_since) max_m FROM activity GROUP BY cohort)
        SELECT c.cohort, c.n size, r.max_m months_active
        FROM cohort_size c JOIN retained r USING(cohort) ORDER BY c.cohort""")

    # channel mix
    agg["channel"] = q("""
        SELECT channel, ROUND(SUM(sales_amount)) revenue, COUNT(*) lines
        FROM fact_sales GROUP BY channel ORDER BY revenue""")

    # weekend vs weekday
    agg["weekend_split"] = q("""
        SELECT dd.is_weekend, ROUND(SUM(fs.sales_amount)) revenue
        FROM fact_sales fs JOIN dim_date dd USING(date_key)
        GROUP BY dd.is_weekend""")

    return agg


def main():
    t0 = datetime.now()
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    log.info("BUILD  | creating star schema DDL...")
    con.executescript(DDL)
    build_dims(con)
    load_facts(con)

    log.info("QUERY  | running warehouse analytics (RFM, YoY, regions)...")
    agg = run_analytics(con)

    out_file = OUT / "aggregates.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False)
    con.close()
    k = agg["kpis"]
    log.info(f"PIPELINE OK in {(datetime.now()-t0).total_seconds():.1f}s | "
             f"{k['orders']:,} orders | ${k['revenue']:,.0f} revenue | "
             f"${k['profit']:,.0f} profit -> {out_file.name}")


if __name__ == "__main__":
    main()
