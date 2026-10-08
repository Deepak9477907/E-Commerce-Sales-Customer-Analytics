"""Complete Olist Pandas analysis: run independently of earlier notebook cells.

Save this file in your project's python folder, with the six Olist CSVs in
the sibling data folder. Run: python ecommerce_analysis_complete.py
Or paste the entire file into one fresh notebook cell and run it.
Requires pandas. All output CSVs go to the project's outputs folder.
SQL benchmarks below come from the results supplied in our project conversation;
they are checks, not values substituted into the calculations.
"""

# %% 1. Imports and file locations
from pathlib import Path
import math
import pandas as pd

# Usually leave these as None. Set explicit paths if your folders differ.
DATA_DIR = None
OUTPUT_DIR = None

FILENAMES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "products": "olist_products_dataset.csv",
}

def locate_data_folder():
    if DATA_DIR is not None:
        candidates = [Path(DATA_DIR).expanduser()]
    else:
        roots = [Path.cwd()]
        if "__file__" in globals():
            roots.insert(0, Path(__file__).resolve().parent)
        candidates = []
        for root in roots:
            candidates.extend([root / "data", root.parent / "data", root])
    for folder in candidates:
        if all((folder / name).is_file() for name in FILENAMES.values()):
            return folder.resolve()
    locations = "\n".join(str(p.resolve()) for p in candidates)
    raise FileNotFoundError(
        "Could not find all six Olist CSVs. Set DATA_DIR at the top of this file "
        "to your data folder. Required files:\n"
        + "\n".join(FILENAMES.values()) + "\nFolders checked:\n" + locations
    )

data_dir = locate_data_folder()
output_dir = Path(OUTPUT_DIR).expanduser().resolve() if OUTPUT_DIR else data_dir.parent / "outputs"
print("Loading CSVs from:", data_dir)
loaded = {name: pd.read_csv(data_dir / filename) for name, filename in FILENAMES.items()}
orders = loaded["orders"]
customers = loaded["customers"]
payments = loaded["payments"]
reviews = loaded["reviews"]
order_items = loaded["order_items"]
products = loaded["products"]

# %% 2. Validate source structure and convert types
required_columns = {
    "orders": ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
               "order_delivered_customer_date", "order_estimated_delivery_date"],
    "customers": ["customer_id", "customer_unique_id", "customer_state"],
    "payments": ["order_id", "payment_value"],
    "reviews": ["order_id", "review_score"],
    "order_items": ["order_id", "product_id", "price"],
    "products": ["product_id", "product_category_name"],
}
for table_name, columns in required_columns.items():
    missing = set(columns) - set(loaded[table_name].columns)
    if missing:
        raise ValueError(f"{table_name}: missing required columns {sorted(missing)}")

for table_name, key in [("orders", "order_id"), ("customers", "customer_id"),
                        ("products", "product_id")]:
    values = loaded[table_name][key]
    if values.isna().any() or values.duplicated().any():
        raise ValueError(f"{table_name}.{key} must be non-missing and unique. Inspect the source; do not blindly drop rows.")

for table_name, key in [("orders", "customer_id"), ("customers", "customer_unique_id"),
                        ("payments", "order_id"), ("order_items", "order_id"),
                        ("order_items", "product_id")]:
    if loaded[table_name][key].isna().any():
        raise ValueError(f"Missing {table_name}.{key}; inspect the source before calculating metrics.")

if "order_item_id" in order_items.columns:
    if order_items.duplicated(["order_id", "order_item_id"]).any():
        raise ValueError("Duplicate order_id/order_item_id pairs: inspect the order_items source.")

date_columns = ["order_purchase_timestamp", "order_approved_at",
                "order_delivered_carrier_date", "order_delivered_customer_date",
                "order_estimated_delivery_date"]
for column in date_columns:
    if column in orders.columns:
        orders[column] = pd.to_datetime(orders[column], errors="raise")
for frame, column in [(payments, "payment_value"), (order_items, "price"), (reviews, "review_score")]:
    frame[column] = pd.to_numeric(frame[column], errors="raise")
    if frame[column].dropna().isin([float("inf"), float("-inf")]).any():
        raise ValueError(f"Infinite values found in {column}.")

# %% 3. Delivery duration, on-time and late classifications
delivered_orders = orders.loc[orders["order_status"] == "delivered"].copy()
valid_delivery_orders = delivered_orders.loc[
    delivered_orders["order_purchase_timestamp"].notna()
    & delivered_orders["order_delivered_customer_date"].notna()
    & (delivered_orders["order_delivered_customer_date"] >= delivered_orders["order_purchase_timestamp"])
].copy()
valid_delivery_orders["delivery_days"] = (
    valid_delivery_orders["order_delivered_customer_date"]
    - valid_delivery_orders["order_purchase_timestamp"]
).dt.total_seconds() / 86400
average_delivery_days = round(valid_delivery_orders["delivery_days"].mean(), 2)

delivery_performance = valid_delivery_orders.loc[
    valid_delivery_orders["order_estimated_delivery_date"].notna()
].copy()
on_time = (
    delivery_performance["order_delivered_customer_date"].dt.normalize()
    <= delivery_performance["order_estimated_delivery_date"].dt.normalize()
)
delivery_performance["delivery_group"] = on_time.map({True: "On time", False: "Late"})
delivery_performance["is_late"] = ~on_time
order_counts = delivery_performance["delivery_group"].value_counts().reindex(["On time", "Late"], fill_value=0)
delivery_summary = order_counts.rename_axis("delivery_group").reset_index(name="order_count")
delivery_summary["percentage"] = (
    delivery_summary["order_count"] / len(delivery_performance) * 100
).round(2) if len(delivery_performance) else float("nan")

# %% 4. State delivery performance -- always rebuilt here
delivery_with_customers = delivery_performance.merge(
    customers[["customer_id", "customer_state"]],
    on="customer_id", how="left", validate="many_to_one", indicator=True
)
unmatched_delivery_customers = int(delivery_with_customers["_merge"].eq("left_only").sum())
delivery_with_customers = delivery_with_customers.drop(columns="_merge")
state_summary = delivery_with_customers.groupby("customer_state", dropna=False).agg(
    orders_analyzed=("order_id", "size"), late_orders=("is_late", "sum")
).reset_index()
state_summary["late_percentage"] = (
    state_summary["late_orders"] / state_summary["orders_analyzed"] * 100
).round(2)
state_delivery_summary = state_summary.loc[state_summary["orders_analyzed"] >= 100].sort_values(
    ["late_percentage", "late_orders"], ascending=[False, False]
).reset_index(drop=True)

# %% 5. Reviews versus delivery: each reviewed order has equal weight
order_avg_reviews = reviews.loc[reviews["review_score"].notna()].groupby(
    "order_id"
)["review_score"].mean().reset_index(name="order_avg_score")
delivery_reviews = delivery_performance[["order_id", "delivery_group"]].merge(
    order_avg_reviews, on="order_id", how="inner", validate="one_to_one"
)
delivery_review_summary = delivery_reviews.groupby("delivery_group").agg(
    reviewed_orders=("order_id", "nunique"), avg_review_score=("order_avg_score", "mean")
).reindex(["On time", "Late"])
delivery_review_summary["reviewed_orders"] = delivery_review_summary["reviewed_orders"].fillna(0).astype(int)
delivery_review_summary["avg_review_score"] = delivery_review_summary["avg_review_score"].round(2)
delivery_review_summary = delivery_review_summary.rename_axis("delivery_group").reset_index()

# %% 6. Sum payments per order before calculating the average
# min_count=1 preserves a missing total if all an order's payments are missing.
order_payment_totals = payments.groupby("order_id")["payment_value"].sum(
    min_count=1
).reset_index(name="total_payment_value")
average_payment_value = round(order_payment_totals["total_payment_value"].mean(), 2)
avg_payment_per_order = average_payment_value

# %% 7. Repeat customers: ALL delivered orders, irrespective of delivery dates
delivered_customer_orders = delivered_orders.merge(
    customers[["customer_id", "customer_unique_id"]],
    on="customer_id", how="left", validate="many_to_one"
)
unmatched_repeat_customers = int(delivered_customer_orders["customer_unique_id"].isna().sum())
customer_order_counts = delivered_customer_orders.groupby("customer_unique_id")["order_id"].nunique().reset_index(name="total_orders")
total_customers = len(customer_order_counts)
repeat_customers = int(customer_order_counts["total_orders"].gt(1).sum())
repeat_customer_percentage = round(100 * repeat_customers / total_customers, 2) if total_customers else float("nan")

# %% 8. Delivered merchandise sales and order review scores by category
delivered_items = order_items.merge(
    products[["product_id", "product_category_name"]],
    on="product_id", how="left", validate="many_to_one"
).merge(delivered_orders[["order_id"]], on="order_id", how="inner", validate="many_to_one")
category_sales = delivered_items.groupby("product_category_name", dropna=False).agg(
    total_merchandise_sales_value=("price", lambda values: values.sum(min_count=1)),
    delivered_orders=("order_id", "nunique")
)
# Sales use all delivered items. Review averaging uses one row per order/category.
category_order_scores = delivered_items[["product_category_name", "order_id"]].drop_duplicates().merge(
    order_avg_reviews, on="order_id", how="left", validate="many_to_one"
)
category_scores = category_order_scores.groupby("product_category_name", dropna=False).agg(
    reviewed_orders=("order_avg_score", "count"),
    average_review_score=("order_avg_score", "mean")
)
category_summary = category_sales.join(category_scores, how="left", validate="one_to_one").reset_index()
category_summary["review_coverage_percentage"] = (
    category_summary["reviewed_orders"] / category_summary["delivered_orders"] * 100
)
category_summary = category_summary.sort_values(
    ["total_merchandise_sales_value", "product_category_name"], ascending=[False, True], na_position="last"
).reset_index(drop=True)
# An unknown category remains visible in category_summary but is not a named category.
top_categories = category_summary.loc[category_summary["product_category_name"].notna()].head(10).copy()
priority_categories = top_categories.sort_values(
    ["average_review_score", "total_merchandise_sales_value"],
    ascending=[True, False], na_position="last"
).reset_index(drop=True)
# Rank using full precision, then round for presentation.
category_summary = category_summary.round(2)
top_categories = top_categories.round(2)
priority_categories = priority_categories.round(2)

# %% 9. Monthly payment totals and calendar-aware month-over-month growth
# All statuses; payments attributed to order PURCHASE month, not payment date.
orders_with_payments = order_payment_totals.merge(
    orders[["order_id", "order_purchase_timestamp"]],
    on="order_id", how="inner", validate="one_to_one"
)
orders_with_payments = orders_with_payments.loc[orders_with_payments["order_purchase_timestamp"].notna()].copy()
orders_with_payments["purchase_month"] = orders_with_payments["order_purchase_timestamp"].dt.to_period("M")
monthly_payments = orders_with_payments.groupby("purchase_month")["total_payment_value"].sum(
    min_count=1
).reset_index().sort_values("purchase_month").reset_index(drop=True)
consecutive_months = monthly_payments["purchase_month"].shift(1).eq(monthly_payments["purchase_month"] - 1)
monthly_payments["previous_month_payment"] = monthly_payments["total_payment_value"].shift(1).where(consecutive_months)
previous_payment = monthly_payments["previous_month_payment"]
denominator = previous_payment.where(previous_payment.ne(0))
monthly_payments["mom_growth_percentage"] = (
    (monthly_payments["total_payment_value"] - previous_payment) / denominator * 100
).round(2)
monthly_payments = monthly_payments.round(2)

# Coverage information helps identify sparse boundary months; it does not prove
# that a monthly extract is complete. Missing months are NOT filled with zero.
monthly_coverage = orders_with_payments.groupby("purchase_month").agg(
    paid_orders=("order_id", "nunique"),
    first_purchase=("order_purchase_timestamp", "min"),
    last_purchase=("order_purchase_timestamp", "max")
).reset_index()
if len(monthly_payments):
    full_calendar = pd.period_range(monthly_payments["purchase_month"].min(), monthly_payments["purchase_month"].max(), freq="M")
    absent_months = full_calendar.difference(pd.PeriodIndex(monthly_payments["purchase_month"]))
else:
    absent_months = pd.PeriodIndex([], freq="M")
missing_months = pd.DataFrame({"missing_purchase_month": absent_months.astype(str)})

# %% 10. Validation, KPI summaries and exports
review_lookup = delivery_review_summary.set_index("delivery_group")
benchmark_rows = [
    ("Average delivery days", average_delivery_days, 12.56),
    ("Average payment per order", average_payment_value, 160.99),
    ("Delivered customers", total_customers, 93358),
    ("Repeat customers", repeat_customers, 2801),
    ("Repeat customer percentage", repeat_customer_percentage, 3.00),
    ("Delivery orders analyzed", len(delivery_performance), 96470),
    ("On-time orders", int(order_counts["On time"]), 89936),
    ("Late orders", int(order_counts["Late"]), 6534),
    ("Reviewed on-time orders", review_lookup.loc["On time", "reviewed_orders"], 89443),
    ("Reviewed late orders", review_lookup.loc["Late", "reviewed_orders"], 6381),
    ("On-time average review", review_lookup.loc["On time", "avg_review_score"], 4.29),
    ("Late average review", review_lookup.loc["Late", "avg_review_score"], 2.27),
]
validation_report = pd.DataFrame(benchmark_rows, columns=["metric", "python_value", "sql_value"])
validation_report["python_value"] = validation_report["python_value"].round(2)
validation_report["difference"] = (validation_report["python_value"] - validation_report["sql_value"]).round(2)
validation_report["status"] = validation_report["difference"].eq(0).map({True: "PASS", False: "CHECK"})

def same_amount(a, b):
    if pd.isna(a) or pd.isna(b):
        return bool(pd.isna(a) and pd.isna(b))
    return math.isclose(float(a), float(b), rel_tol=0, abs_tol=0.01)

quality_checks = [
    ("Delivery rows preserved in customer join", len(delivery_with_customers) == len(delivery_performance)),
    ("All delivery customer IDs matched", unmatched_delivery_customers == 0),
    ("All delivered customer identities matched", unmatched_repeat_customers == 0),
    ("All item order IDs matched", order_items["order_id"].isin(orders["order_id"]).all()),
    ("All item product IDs matched", order_items["product_id"].isin(products["product_id"]).all()),
    ("All payment order IDs matched", payments["order_id"].isin(orders["order_id"]).all()),
    ("Payment amounts non-missing", payments["payment_value"].notna().all()),
    ("Item prices non-missing", order_items["price"].notna().all()),
    ("Non-missing review scores between 1 and 5", reviews["review_score"].dropna().between(1, 5).all()),
    ("On-time plus late equals analyzed orders", int(order_counts.sum()) == len(delivery_performance)),
    ("State counts include all analyzed orders", int(state_summary["orders_analyzed"].sum()) == len(delivery_performance)),
    ("Order totals preserve payment sum", same_amount(order_payment_totals["total_payment_value"].sum(min_count=1), payments["payment_value"].sum(min_count=1))),
    ("Category totals preserve delivered item sales", same_amount(category_sales["total_merchandise_sales_value"].sum(min_count=1), delivered_items["price"].sum(min_count=1))),
    ("Category reviews do not exceed category orders", category_summary["reviewed_orders"].le(category_summary["delivered_orders"]).all()),
    ("Monthly sums preserve matched dated order payments", same_amount(monthly_payments["total_payment_value"].sum(min_count=1), orders_with_payments["total_payment_value"].sum(min_count=1))),
    ("Calendar gaps have missing previous values and growth", monthly_payments.loc[~consecutive_months, ["previous_month_payment", "mom_growth_percentage"]].isna().all().all()),
    ("Zero previous payments have missing growth", monthly_payments.loc[previous_payment.eq(0), "mom_growth_percentage"].isna().all()),
    ("No infinite growth values", not monthly_payments["mom_growth_percentage"].isin([float("inf"), float("-inf")]).any()),
]
data_quality_report = pd.DataFrame(quality_checks, columns=["check", "passed"])
data_quality_report["status"] = data_quality_report["passed"].map({True: "PASS", False: "CHECK"})

data_quality_counts = pd.DataFrame([
    ("Delivered orders missing purchase timestamp", int(delivered_orders["order_purchase_timestamp"].isna().sum())),
    ("Delivered orders missing actual delivery timestamp", int(delivered_orders["order_delivered_customer_date"].isna().sum())),
    ("Delivered orders with delivery before purchase", int((delivered_orders["order_delivered_customer_date"] < delivered_orders["order_purchase_timestamp"]).sum())),
    ("Valid-duration orders missing estimated delivery", int(valid_delivery_orders["order_estimated_delivery_date"].isna().sum())),
    ("Delivery orders without usable reviews", len(delivery_performance) - len(delivery_reviews)),
    ("Delivered item rows without category names", int(delivered_items["product_category_name"].isna().sum())),
    ("Payment orders missing purchase timestamp", int(order_payment_totals.merge(orders[["order_id", "order_purchase_timestamp"]], on="order_id", how="inner", validate="one_to_one")["order_purchase_timestamp"].isna().sum())),
    ("Review rows missing order_id", int(reviews["order_id"].isna().sum())),
    ("Review rows missing review_score", int(reviews["review_score"].isna().sum())),
], columns=["description", "row_count"])

kpi_summary = validation_report[["metric", "python_value"]].rename(columns={"python_value": "value"}).copy()
input_manifest = pd.DataFrame([
    (name, FILENAMES[name], len(frame), len(frame.columns))
    for name, frame in loaded.items()
], columns=["table", "source_filename", "rows", "columns"])

tables_to_export = {
    "delivery_summary": delivery_summary,
    "state_summary_all": state_summary,
    "state_delivery_summary": state_delivery_summary,
    "delivery_review_summary": delivery_review_summary,
    "order_payment_totals": order_payment_totals,
    "customer_order_counts": customer_order_counts,
    "category_summary": category_summary,
    "top_categories": top_categories,
    "priority_categories": priority_categories,
    "monthly_payments": monthly_payments,
    "monthly_coverage": monthly_coverage,
    "missing_months": missing_months,
    "kpi_summary": kpi_summary,
    "validation_report": validation_report,
    "data_quality_report": data_quality_report,
    "data_quality_counts": data_quality_counts,
    "input_manifest": input_manifest,
}
output_dir.mkdir(parents=True, exist_ok=True)
for name, table in tables_to_export.items():
    export_table = table.copy()
    if "purchase_month" in export_table.columns:
        export_table["purchase_month"] = export_table["purchase_month"].astype(str)
    export_table.to_csv(output_dir / f"{name}.csv", index=False)

notes = """Metric definitions and limits
- Merchandise sales = item price sum for delivered orders; excludes freight.
- Recorded payments are not profit or confirmed accounting revenue.
- Delivery duration uses elapsed seconds / 86400; invalid/missing date pairs excluded.
- On-time delivery compares calendar dates, inclusive of the estimated date.
- State ranking includes states with at least 100 eligible delivery orders.
- Repeat customers have >1 distinct delivered order, using customer_unique_id.
- The repeat rate describes observed purchases, not churn or lifetime retention.
- Reviews are averaged within each order first; category averages count each order once per category.
- Category sales include unreviewed orders; review averages exclude missing scores.
- Reviews describe whole orders, not individual product satisfaction or causation.
- Unknown categories remain in category_summary; top/priority tables use named categories.
- Priority categories = 10 highest merchandise sales, ordered by review average ascending.
- Review counts and coverage accompany averages; no minimum review-count threshold is applied.
- Monthly payments use purchase month and ALL order statuses.
- Calendar gaps and zero previous-month amounts give missing MoM growth, not zero growth.
- Sparse boundary months and tiny bases require care before interpreting growth.
- SQL benchmarks are the earlier reported outputs, not freshly queried SQL results.
- PASS applies only to the listed checks; it is not proof of complete data accuracy.
- Rerunning this script replaces these generated output files, not the source CSVs.
"""
(output_dir / "analysis_notes.txt").write_text(notes, encoding="utf-8")
all_checks_passed = bool(validation_report["status"].eq("PASS").all() and data_quality_report["passed"].all())
status_text = "PASS: all listed checks passed." if all_checks_passed else "CHECK: review validation_report.csv and data_quality_report.csv before finalizing findings."
(output_dir / "run_status.txt").write_text(status_text + "\n", encoding="utf-8")

print("\nSQL benchmark checks:")
print(validation_report.to_string(index=False))
print("\nPriority categories (top 10 named categories by sales; lowest reviews first):")
print(priority_categories.to_string(index=False))
print(f"\nSaved {len(tables_to_export)} CSV files plus notes and status to: {output_dir.resolve()}")
print(status_text)
print("Pandas coding is complete. Power BI and project documentation are separate next steps.")
