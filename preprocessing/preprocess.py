"""수집된 금융 뉴스의 정규화와 중복 제거를 담당한다."""

import re
from typing import Any


TEXT_FIELDS = ("title", "content", "press", "published_at", "url")


def normalize_news(articles: list[dict[str, Any]]) -> list[dict[str, str]]:
    """뉴스 텍스트를 정리하고 URL 기준으로 중복을 제거한다.

    Collector의 원본 데이터는 변경하지 않는다. 저장과 임베딩 단계에서 사용할
    새 리스트만 반환한다.
    """
    normalized_articles: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for index, article in enumerate(articles):
        normalized = {
            field: _normalize_text(article.get(field), field, index)
            for field in TEXT_FIELDS
        }

        if normalized["url"] in seen_urls:
            continue

        seen_urls.add(normalized["url"])
        normalized_articles.append(normalized)

    return normalized_articles


def _normalize_text(value: Any, field: str, index: int) -> str:
    """문자열의 연속 공백을 정리하고 빈 필드를 거부한다."""
    if not isinstance(value, str):
        raise ValueError(f"{index}번 뉴스의 {field} 필드가 문자열이 아닙니다.")

    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        raise ValueError(f"{index}번 뉴스의 {field} 필드가 비어 있습니다.")
    return normalized
