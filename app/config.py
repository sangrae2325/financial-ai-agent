import os

PROJECT_ID = os.getenv("GCP_PROJECT_ID")

BUCKET_NAME = os.getenv("GCP_BUCKET")

DATASET = "financial_ai"

EXCHANGE_TABLE = "exchange_rates"

METADATA_TABLE = "ingest_metadata"