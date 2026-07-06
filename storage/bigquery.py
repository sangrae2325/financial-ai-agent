"""
BigQuery 업로드 모듈
"""
import json
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from google.cloud import bigquery

from app.config import (
    PROJECT_ID,
    DATASET,
    EXCHANGE_TABLE,
)

client = bigquery.Client(project=PROJECT_ID)

def ensure_exchange_table() -> str:
    """
    exchange_rates 테이블이 없으면 생성한다.
    """

    table_id = f"{PROJECT_ID}.{DATASET}.{EXCHANGE_TABLE}"

    schema = [
        bigquery.SchemaField("base_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("currency", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("rate", "FLOAT", mode="REQUIRED"),
        bigquery.SchemaField("fetched_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("gcs_uri", "STRING", mode="REQUIRED"),
    ]

    table = bigquery.Table(
        table_id,
        schema=schema,
    )

    client.create_table(
        table,
        exists_ok=True,
    )

    print(f"Exchange Table Ready : {table_id}")

    return table_id

def upload_exchange(
    file_path: str,
    gcs_uri: str,
) -> None:
    """
    환율 JSON 파일을 BigQuery에 적재한다.

    Args:
        file_path: 로컬 JSON 파일 경로
        gcs_uri: 업로드된 GCS URI
    """
    with open(file_path, "r", encoding="utf-8") as f:
        exchange = json.load(f)

    table_id = ensure_exchange_table()
    rows = []

    raw_time = exchange.get("time_last_update_utc")

    if raw_time:
        fetched_at = parsedate_to_datetime(raw_time).isoformat()
    else:
        fetched_at = datetime.now(timezone.utc).isoformat()
        
    ingested_at = datetime.now(timezone.utc).isoformat()

    for currency, rate in exchange["rates"].items():

        rows.append(
            {
                "base_code": exchange["base_code"],
                "currency": currency,
                "rate": rate,
                "fetched_at": fetched_at,
                "ingested_at": ingested_at,
                "gcs_uri": gcs_uri,
            }
        )
    

    job = client.load_table_from_json(
        rows,
        table_id,
    )

    job.result()

    print(f"BigQuery Upload Success : {len(rows)} rows")