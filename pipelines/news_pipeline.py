"""금융 뉴스 수집 파이프라인.

Flow
News Collector → Validation → Local → (선택) GCS → BigQuery
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any

from collectors.news import fetch_news
from preprocessing.preprocess import normalize_news
from storage.local import save_json, save_json_to_path
from validation.data_quality import validate_news_payload


DEFAULT_NEWS_PATH = Path("data/news/news.json")
DEFAULT_NEWS_PAGES = 3


def merge_news_articles(
    newly_collected: list[dict[str, Any]], existing: list[dict[str, Any]]
) -> list[dict[str, str]]:
    """새 기사 우선으로 URL 기준 누적 목록을 만든다.

    동일 URL의 기사는 새 수집본을 우선해 제목·본문 수정도 다음 인덱싱 때 반영할
    수 있게 한다. normalize_news는 공백 정리와 중복 제거를 함께 담당한다.
    """
    return normalize_news(newly_collected + existing)


def run_news_pipeline(
    *,
    upload_to_cloud: bool = True,
    run_date: str | None = None,
    pages: int = DEFAULT_NEWS_PAGES,
) -> None:
    """뉴스를 수집·검증·로컬 저장하고, 선택적으로 클라우드에 적재한다.

    로컬 모드는 RAG 인덱스 실습을 GCP 설정 없이 재현할 수 있게 한다.
    운영 적재에서는 ``upload_to_cloud=True``로 GCS와 BigQuery까지 이어진다.
    """
    newly_collected = fetch_news(pages=pages)
    validate_news_payload(newly_collected)

    snapshot_date = run_date or date.today().isoformat()
    existing = _load_existing_news(DEFAULT_NEWS_PATH)
    articles = merge_news_articles(newly_collected, existing)

    snapshot_path = Path("data/news/raw") / snapshot_date / "news.json"
    save_json_to_path(newly_collected, snapshot_path)

    file_path = save_json(articles, "news")
    if not upload_to_cloud:
        print(
            "News Local Pipeline Success : "
            f"pages={pages}, new={len(newly_collected)}, total={len(articles)} articles"
        )
        print(f"Raw Snapshot : {snapshot_path}")
        print(f"Local Path : {file_path}")
        return

    # 로컬 모드에서는 GCP Client를 만들지 않도록 클라우드 모듈을 지연 import한다.
    from storage.bigquery import upload_news
    from storage.gcs import upload_json

    gcs_uri = upload_json(file_path, "news")
    upload_news(file_path, gcs_uri)

    print(
        "News Pipeline Success : "
        f"pages={pages}, new={len(newly_collected)}, total={len(articles)} articles"
    )
    print(f"Raw Snapshot : {snapshot_path}")
    print(f"GCS URI : {gcs_uri}")


def _load_existing_news(path: Path) -> list[dict[str, Any]]:
    """누적 뉴스 파일이 있으면 읽고, 첫 실행이면 빈 목록을 반환한다."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, list):
        raise ValueError(f"누적 뉴스 파일이 리스트가 아닙니다: {path}")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="금융 뉴스 수집 파이프라인")
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="GCS·BigQuery 적재 없이 로컬 JSON 저장까지만 실행",
    )
    parser.add_argument(
        "--run-date",
        help="원본 스냅샷 저장 날짜(YYYY-MM-DD). 기본값은 오늘 날짜",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=DEFAULT_NEWS_PAGES,
        help=f"네이버 금융 뉴스에서 수집할 페이지 수(기본값: {DEFAULT_NEWS_PAGES})",
    )
    args = parser.parse_args()
    run_news_pipeline(
        upload_to_cloud=not args.local_only,
        run_date=args.run_date,
        pages=args.pages,
    )
