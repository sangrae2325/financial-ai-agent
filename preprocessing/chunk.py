"""정규화된 금융 뉴스를 임베딩용 청크로 분할한다."""

import hashlib
import re
from typing import Any


def chunk_news(
    articles: list[dict[str, str]],
    chunk_size: int = 700,
    overlap: int = 100,
) -> list[dict[str, Any]]:
    """기사 본문을 겹치는 청크로 나누고 검색 메타데이터를 보존한다."""
    _validate_chunk_options(chunk_size, overlap)

    chunks: list[dict[str, Any]] = []
    for article_index, article in enumerate(articles):
        document_id = hashlib.sha256(article["url"].encode("utf-8")).hexdigest()[:16]
        body_chunks = _split_text(article["content"], chunk_size, overlap)

        published_date = _extract_published_date(article["published_at"])
        for chunk_index, body_chunk in enumerate(body_chunks):
            chunks.append(
                {
                    "chunk_id": f"news_{document_id}_chunk_{chunk_index}",
                    "document_id": document_id,
                    "chunk_index": chunk_index,
                    "text": f"제목: {article['title']}\n본문: {body_chunk}",
                    "metadata": {
                        "article_index": article_index,
                        "title": article["title"],
                        "press": article["press"],
                        "published_at": article["published_at"],
                        "published_date": published_date,
                        "published_date_key": int(published_date.replace("-", "")) if published_date else 0,
                        "url": article["url"],
                    },
                }
            )

    return chunks


def _extract_published_date(published_at: str) -> str:
    """네이버 표기 시각에서 정렬·필터 가능한 YYYY-MM-DD 날짜를 만든다."""
    match = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", published_at)
    if match is None:
        return ""
    year, month, day = (int(value) for value in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def _validate_chunk_options(chunk_size: int, overlap: int) -> None:
    """청크 길이와 중복 구간이 유효한지 검사한다."""
    if chunk_size <= 0:
        raise ValueError("chunk_size는 1 이상이어야 합니다.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap은 0 이상 chunk_size 미만이어야 합니다.")


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """문자 수 기준으로 본문을 겹치게 나눈다."""
    step = chunk_size - overlap
    return [
        text[start : start + chunk_size]
        for start in range(0, len(text), step)
        if text[start : start + chunk_size]
    ]
