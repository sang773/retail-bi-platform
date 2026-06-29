# Data Quality Report — Olist Brazilian E-Commerce

**Dataset:** Olist Public E-Commerce Dataset  
**Date:** 2026-06-25  
**Analyst:** Sangeet Gaire

---

## 1. Table Inventory

| Table | Rows | Columns |
|---|---|---|
| orders | 99,441 | 8 |
| order_items | 112,650 | 7 |
| customers | 99,441 | 5 |
| products | 32,951 | 9 |
| sellers | 3,095 | 4 |
| payments | 103,886 | 5 |
| reviews | 99,224 | 7 |
| geolocation | 1,000,163 | 5 |
| category_translation | 71 | 2 |

---

## 2. Null Values by Table

### orders
| Column | Null Count | % Null | Notes |
|---|---|---|---|
| order_approved_at | 160 | 0.2% | Orders not yet approved |
| order_delivered_carrier_date | 1,783 | 1.8% | Not handed to carrier yet |
| order_delivered_customer_date | 2,965 | 3.0% | **Intentional** — canceled/shipped orders have no delivery date. Handle by keeping nulls for non-delivered orders. |

### products
| Column | Null Count | % Null | Notes |
|---|---|---|---|
| product_category_name | 610 | 1.9% | Unknown category — impute as "unknown" |
| product_name_lenght | 610 | 1.9% | Same 610 rows as above |
| product_description_lenght | 610 | 1.9% | Same 610 rows |
| product_photos_qty | 610 | 1.9% | Same 610 rows |
| product_weight_g | 2 | 0.0% | Minor — drop or impute with median |
| product_length_cm | 2 | 0.0% | Same 2 rows |
| product_height_cm | 2 | 0.0% | Same 2 rows |
| product_width_cm | 2 | 0.0% | Same 2 rows |

### reviews
| Column | Null Count | % Null | Notes |
|---|---|---|---|
| review_comment_title | 87,656 | 88.3% | **Expected** — title is optional; most customers skip it |
| review_comment_message | 58,247 | 58.7% | **Expected** — free-text comment is optional |

### order_items, customers, sellers, payments, geolocation
No nulls.

---

## 3. Wrong Data Types

All date/timestamp columns across every table are stored as `object` (string) — they must be converted to `datetime64`.

| Table | Column | Current Type | Should Be |
|---|---|---|---|
| orders | order_purchase_timestamp | string | datetime |
| orders | order_approved_at | string | datetime |
| orders | order_delivered_carrier_date | string | datetime |
| orders | order_delivered_customer_date | string | datetime |
| orders | order_estimated_delivery_date | string | datetime |
| order_items | shipping_limit_date | string | datetime |
| reviews | review_creation_date | string | datetime |
| reviews | review_answer_timestamp | string | datetime |

**Action:** Apply `pd.to_datetime(..., errors='coerce')` to all date columns at load time.

---

## 4. Outliers

### Price (order_items)
| Metric | Value |
|---|---|
| Mean | $120.65 |
| Median | $74.99 |
| 75th percentile | $134.90 |
| Max | **$6,735.00** |

- 3 items exceed $5,000 — they are real luxury goods (computers, instruments), not data errors.
- Distribution is **heavily right-skewed**; use log scale for histogram.

### Payment Value (payments)
| Metric | Value |
|---|---|
| Median | $100.00 |
| Max | **$13,664.08** |

- Max payment of ~$13,664 corresponds to installment-split purchases of high-value items. Valid.

### Order Value Notes
- No single order reaches $50,000 — the dataset does not contain that extreme an outlier.
- The max item price is $6,735 (single product).

---

## 5. Categorical Issues

### Order Status Distribution
| Status | Count |
|---|---|
| delivered | 96,478 |
| shipped | 1,107 |
| canceled | 625 |
| unavailable | 609 |
| invoiced | 314 |
| processing | 301 |
| created | 5 |
| approved | 2 |

- 96.9% of orders are delivered — dataset is heavily delivery-complete.
- Canceled orders (~625) will have null delivery dates; filter them out of delivery-time analyses.

### Product Categories
- 73 unique categories stored in **Portuguese**.
- 610 products (1.9%) have no category — impute as `"unknown"`.
- Translation table covers 71 of 73 categories; 2 may remain in Portuguese after join.
- **Action:** Left-join `products` to `category_translation` on `product_category_name`.

---

## 6. Geolocation Duplicates

| Metric | Value |
|---|---|
| Total rows | 1,000,163 |
| Unique zip codes | 19,015 |
| Duplicate rows (same zip) | 981,148 |

- Each zip code has an average of ~52 lat/lng entries (multiple measurement points per zip area).
- **Action:** Deduplicate by taking the mean lat/lng per zip code before joining to customers/sellers.

---

## 7. Foreign Key Integrity

| Relationship | Matched | Total | % Match |
|---|---|---|---|
| orders → customers | 99,441 | 99,441 | 100% |
| order_items → orders | 112,650 | 112,650 | 100% |
| order_items → products | 112,650 | 112,650 | 100% |
| order_items → sellers | 112,650 | 112,650 | 100% |
| payments → orders | 103,886 | 103,886 | 100% |
| reviews → orders | 99,224 | 99,224 | 100% |

All foreign keys resolve cleanly — no orphaned records.

**Note:** `payments` (103,886) > `orders` (99,441) because a single order can have multiple payment rows (e.g., voucher + credit card split).

---

## 8. Schema / Entity Relationship

```
customers (customer_id PK)
    └── orders (customer_id FK, order_id PK)
            ├── order_items (order_id FK, product_id FK, seller_id FK)
            │       └── products (product_id PK)
            │               └── category_translation (product_category_name FK)
            │       └── sellers (seller_id PK)
            ├── payments (order_id FK)
            └── reviews (order_id FK)

geolocation (geolocation_zip_code_prefix)
    ← joined to customers and sellers via zip_code_prefix
```

---

## 9. Key Findings Summary

| # | Finding | Severity | Action |
|---|---|---|---|
| 1 | All date columns stored as strings | High | Convert to datetime at load |
| 2 | Delivery date null for 2,965 orders | Medium | Expected for non-delivered; filter by status |
| 3 | Product categories in Portuguese | Medium | Join to translation table |
| 4 | Geolocation has 981K duplicate zip rows | Medium | Deduplicate (mean lat/lng per zip) |
| 5 | 610 products missing category | Low | Impute as "unknown" |
| 6 | Price skewed right (max $6,735) | Low | Use log scale in charts; not data errors |
| 7 | Reviews 88% missing comment title | Low | Expected; ignore for NLP analysis |
| 8 | All foreign keys 100% intact | ✅ Good | No action needed |
