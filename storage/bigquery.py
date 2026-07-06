import json
from datetime import datetime, timezone

from google.cloud import bigquery

from app.config import (
    PROJECT_ID,
    DATASET,
    EXCHANGE_TABLE,
)

client = bigquery.Client(project=PROJECT_ID)

def upload_exchange_rates(
        json_path: str,
        gcs_uri: str,
):
    """
    환율 JSON을 BigQuery에 적재한다.
    """

    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    
    exchange = payload
    
    rows = []

    for currency, rate in exchange["rates"].items():

        rows.append(
            {
                "base_code": exchange["base_code"],
                "currency": currency,
                "rate": rate,
                "data_source": "https://open.er-api.com/v6/latest/USD",
                "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                "ingested_at_utc": datetime.now(timezone.utc).isoformat(),
                "gcs_uri": gcs_uri,
            }
        )
    table_id = f"{PROJECT_ID}.{DATASET}.{EXCHANGE_TABLE}"

    job = client.load_table_from_json(rows, table_id)

    job.result()

    print("BigQuery Upload Success")