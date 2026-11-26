"""Load the Veridian master data into BigQuery.

Creates a dataset and loads five tables from data/raw using load jobs
(the BigQuery sandbox does not allow INSERT statements). Re-running
replaces the tables, which is also how to refresh them after the
sandbox's 60 day expiry. answer_key.csv is never loaded.
All data is fictional.

Run from the project root with:  python -m src.loaders.bigquery_load
"""

import os
import warnings
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

warnings.filterwarnings("ignore", message=".*without a quota project.*")

DATASET = "veridian_optics"
LOCATION = "europe-west2"  # London. Use "EU" if this location is refused.
RAW = Path("data/raw")

S = bigquery.SchemaField

TABLES = {
    "accounts": ("accounts.csv", [
        S("account_id", "STRING"),
        S("name", "STRING"),
        S("account_type", "STRING"),
        S("parent_group", "STRING"),
        S("region", "STRING"),
        S("size", "STRING"),
        S("customer_since", "DATE"),
    ]),
    "installed_base": ("installed_base.csv", [
        S("asset_id", "STRING"),
        S("account_id", "STRING"),
        S("product", "STRING"),
        S("product_line", "STRING"),
        S("serial_number", "STRING"),
        S("consumable_type", "STRING"),
        S("install_date", "DATE"),
        S("warranty_end", "DATE"),
        S("service_contract", "BOOL"),
    ]),
    "consumable_orders": ("consumable_orders.csv", [
        S("order_id", "STRING"),
        S("account_id", "STRING"),
        S("asset_id", "STRING"),
        S("consumable_type", "STRING"),
        S("order_date", "DATE"),
        S("quantity", "INT64"),
        S("unit_price", "FLOAT64"),
        S("order_value", "FLOAT64"),
    ]),
    "account_events": ("account_events.csv", [
        S("event_id", "STRING"),
        S("account_id", "STRING"),
        S("event_type", "STRING"),
        S("event_date", "DATE"),
    ]),
    "web_sessions": ("web_sessions.csv", [
        S("session_id", "STRING"),
        S("session_start", "DATETIME"),
        S("source", "STRING"),
        S("landing_page", "STRING"),
        S("pages_viewed", "INT64"),
        S("duration_seconds", "INT64"),
        S("device", "STRING"),
        S("country", "STRING"),
    ]),
    "campaigns": ("campaigns.csv", [
        S("campaign_id", "STRING"),
        S("name", "STRING"),
        S("campaign_type", "STRING"),
        S("send_date", "DATE"),
    ]),
    "email_activity": ("email_activity.csv", [
        S("email_id", "STRING"),
        S("campaign_id", "STRING"),
        S("contact_id", "STRING"),
        S("send_date", "DATE"),
        S("delivered", "BOOL"),
        S("opened", "BOOL"),
        S("clicked", "BOOL"),
        S("unsubscribed", "BOOL"),
    ]),
    "webinar_attendance": ("webinar_attendance.csv", [
        S("registration_id", "STRING"),
        S("webinar_name", "STRING"),
        S("webinar_date", "DATE"),
        S("contact_id", "STRING"),
        S("account_id", "STRING"),
        S("registered_date", "DATE"),
        S("attended", "BOOL"),
    ]),
    "demo_requests": ("demo_requests.csv", [
        S("demo_id", "STRING"),
        S("contact_id", "STRING"),
        S("account_id", "STRING"),
        S("request_date", "DATE"),
        S("product_interest", "STRING"),
        S("request_source", "STRING"),
    ]),
}


def count_rows(path):
    """Count data rows in a CSV file (everything except the header)."""
    with open(path, encoding="utf-8") as f:
        return sum(1 for _ in f) - 1


def main():
    load_dotenv()
    project = os.environ.get("GCP_PROJECT_ID")
    if not project:
        raise SystemExit("GCP_PROJECT_ID is missing from your .env file.")

    client = bigquery.Client(project=project, location=LOCATION)

    dataset = bigquery.Dataset(f"{project}.{DATASET}")
    dataset.location = LOCATION
    client.create_dataset(dataset, exists_ok=True)
    print(f"Dataset {project}.{DATASET} ready in {LOCATION}")
    print()

    for table_name, (file_name, schema) in TABLES.items():
        path = RAW / file_name
        table_id = f"{project}.{DATASET}.{table_name}"
        config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        with open(path, "rb") as f:
            job = client.load_table_from_file(f, table_id, job_config=config)
        job.result()

        expected = count_rows(path)
        loaded = client.get_table(table_id).num_rows
        status = "OK" if loaded == expected else f"MISMATCH (file has {expected})"
        print(f"{table_name:<18}{loaded:>8} rows   {status}")

    print()
    print("Test query: consumable orders by type")
    rows = client.query(
        f"""
        SELECT consumable_type,
               COUNT(*) AS orders,
               ROUND(SUM(order_value)) AS total_value
        FROM `{project}.{DATASET}.consumable_orders`
        GROUP BY consumable_type
        ORDER BY total_value DESC
        """
    ).result()
    for r in rows:
        print(f"  {r.consumable_type:<18}{r.orders:>6} orders   £{r.total_value:,.0f}")


if __name__ == "__main__":
    main()