"""국내 핵심 종목·코스피 시세를 날짜별 원본과 누적 파일에 저장한다."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from collectors.stock import fetch_stock
from storage.local import save_json, save_json_to_path
from validation.data_quality import validate_stock_payload


DEFAULT_STOCK_PATH = Path("data/stocks/stocks.json")


def merge_stock_records(
    newly_collected: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """symbol·거래일 기준으로 시세를 누적하고 새 수집 결과를 우선한다."""
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for record in existing + newly_collected:
        merged[(str(record["symbol"]), str(record["date"]))] = record
    return sorted(merged.values(), key=lambda item: (item["date"], item["symbol"]))


def run_stock_pipeline(*, run_date: str | None = None) -> None:
    """시세를 수집·검증·로컬 누적 저장한다."""
    newly_collected = fetch_stock()
    validate_stock_payload(newly_collected)

    existing = _load_existing_records(DEFAULT_STOCK_PATH)
    records = merge_stock_records(newly_collected, existing)
    snapshot_date = run_date or date.today().isoformat()
    snapshot_path = Path("data/stocks/raw") / snapshot_date / "stocks.json"
    save_json_to_path(newly_collected, snapshot_path)
    file_path = save_json(records, "stocks")

    print(
        "Stock Local Pipeline Success : "
        f"new={len(newly_collected)}, total={len(records)} records"
    )
    print(f"Raw Snapshot : {snapshot_path}")
    print(f"Local Path : {file_path}")


def _load_existing_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError(f"누적 시세 파일이 리스트가 아닙니다: {path}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="금융 시세 로컬 수집 파이프라인")
    parser.add_argument("--run-date", help="원본 스냅샷 저장 날짜(YYYY-MM-DD)")
    args = parser.parse_args()
    run_stock_pipeline(run_date=args.run_date)
