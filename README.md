# 🏛️ WarehouseBI — Sales Data Warehouse (Star Schema + SQL Analytics)

A **data warehousing project**: OLTP-style extracts → Kimball star schema in SQLite (`dim_date`, `dim_customer`, `dim_product`, `fact_sales`) → analytical SQL (RFM via NTILE window functions, YoY/MoM growth, cohort analysis, Pareto customers) → animated BI dashboard.

![python](https://img.shields.io/badge/Python-3.10%2B-blue) ![sql](https://img.shields.io/badge/SQLite-star%20schema-green)

## 🏗️ Architecture

```
OLTP extracts                    STAR SCHEMA (warehouse.db)
┌───────────────────┐            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ sales_extract.csv │            │   dim_date   │   │ dim_customer │   │ dim_product  │
│ customers_extract ├──────────▶ └──────┬───────┘   └──────┬───────┘   └──────┬───────┘
│ products_extract  │  ETL:             └──────────┬───────┴──────────────────┘
└───────────────────┘  surrogate keys              ▼
                       conformed dims       ┌──────────────┐      ┌───────────────┐
                                             │  fact_sales  │────▶ │ Analytical SQL │
                                             │ ~50K lines   │      │ • RFM (NTILE)  │
                                             └──────────────┘      │ • YoY windows  │
                                                                   │ • cohorts      │
                                                                   └───────┬───────┘
                                                                           ▼
                                                                 ┌──────────────────┐
                                                                 │ Animated BI Dash │
                                                                 └──────────────────┘
```

## 🚀 Run It

```bash
pip install -r requirements.txt
python run_all.py
# open dashboard/index.html — or explore data/warehouse.db with any SQL client!
```

## 🧮 The Actual SQL Inside

```sql
-- RFM segmentation with pure window functions
SELECT CASE WHEN frequency_score >= 4 AND monetary_score >= 4 THEN 'Champions' ... END segment,
       COUNT(*), ROUND(SUM(monetary)) revenue
FROM (
  SELECT *, NTILE(5) OVER (ORDER BY last_purchase DESC) recency_score,
            NTILE(5) OVER (ORDER BY frequency)      frequency_score,
            NTILE(5) OVER (ORDER BY monetary)       monetary_score
  FROM rfm_base) GROUP BY segment;

-- Month-over-month growth with LAG()
ROUND(100.0*(revenue - LAG(revenue) OVER (ORDER BY year, month))
      / NULLIF(LAG(revenue) OVER (ORDER BY year, month), 0), 1)
```

Plus recursive CTE date dimension generation, multi-table fact joins with derived profit, channel mix, weekend/weekday split.

## 📊 Dashboard Highlights

- Proportional **RFM segment blocks** (size ∝ revenue, spring pop-in animation)
- Monthly revenue bars + MoM growth line (best month highlighted gold)
- Category performance: revenue bars + margin-% overlay
- Regional revenue with gradient fill + active-customer tooltips
- Customer **cohort activity-span** animated progress rows
- Top-10 customers by lifetime value table with staggered row reveal

## 🧠 Data Engineering Concepts Demonstrated

- **Dimensional modeling** — Kimball 4-step design process
- Surrogate keys, conformed dimensions, recursive-CTE date dimension
- Fact table loading with referential integrity (FOREIGN KEYs)
- Advanced SQL: `NTILE`, `LAG`, `GROUP BY` rollups, recursive CTEs
- RFM customer analytics & cohort behavior analysis
- Warehouse file (`warehouse.db`) portable to any SQL client for exploration

## 💬 LinkedIn Caption

> 🏛️ Built a complete Sales Data Warehouse from scratch!
>
> ✅ Designed a Kimball star schema: dim_date, dim_customer, dim_product + fact_sales
> ✅ Generated the date dimension with a recursive CTE
> ✅ RFM segmentation using NTILE(5) window functions in pure SQL
> ✅ MoM/YoY growth with LAG() over monthly rollups
> ✅ Cohort retention + Pareto customer analysis
> ✅ Animated BI dashboard on top of the warehouse
>
> Tech: Python, Pandas, SQLite, Chart.js — the .db file opens in any SQL client
>
> #DataEngineering #DataWarehousing #SQL #StarSchema #Analytics #DatabaseDesign

## 👤 Author

**Arun Prajapati** — Data Engineer
- GitHub: [github.com/Arun3622](https://github.com/Arun3622)
- Repository: [github.com/Arun3622/WarehouseBI-](https://github.com/Arun3622/WarehouseBI-)


> 🗓️ **Project completed:** August 06, 2026
