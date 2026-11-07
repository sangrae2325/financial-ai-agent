"""
환율 데이터 수집 파이프라인

Flow
Exchange API
    ↓
Validation
    ↓
Local
    ↓
GCS
    ↓
BigQuery
"""

import argparse

from collectors.exchange_rate import fetch_exchange_rate
from storage.local import save_json
from validation.data_quality import validate_exchange_payload


def run_exchange_pipeline(*, upload_to_cloud: bool = True) -> None:
    """
    환율 데이터 수집 파이프라인 실행
    """

    data = fetch_exchange_rate()

    validate_exchange_payload(data)

    file_path = save_json(
        data,
        "exchange",
    )

    if upload_to_cloud:
        # 로컬 전용 실행은 GCP 의존성을 전혀 사용하지 않는다.
        from storage.bigquery import upload_exchange
        from storage.gcs import upload_json

        gcs_uri = upload_json(file_path, "exchange")
        upload_exchange(file_path, gcs_uri)
        print(f"GCS URI : {gcs_uri}")
    print(f"Base : {data['base_code']}")
    print(f"KRW : {data['rates']['KRW']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="환율 수집 파이프라인")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="GCS·BigQuery 적재 없이 로컬 JSON만 갱신합니다.",
    )
    args = parser.parse_args()
    run_exchange_pipeline(upload_to_cloud=not args.local_only)
