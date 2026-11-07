"""
데이터 품질 검증
"""

from typing import Any

class DataQualityError(Exception):
    """데이터 품질 검증 실패"""

def validate_exchange_payload(data: dict[str, Any]) -> None:
    """
    환율 API 응답 검증
    """

    required_fields = (
        "result",
        "base_code",
        "rates",
    )

    for field in required_fields:
        if field not in data:
            raise DataQualityError(f"{field} 필드가 없습니다.")
        
    print("Exchange Rate Validation Success")


def validate_news_payload(data: list[dict[str, Any]]) -> None:
    """수집된 뉴스 기사 목록의 필수 필드를 검증한다."""
    if not isinstance(data, list) or not data:
        raise DataQualityError("뉴스 데이터는 비어 있지 않은 리스트여야 합니다.")

    required_fields = ("title", "content", "press", "published_at", "url")

    for index, article in enumerate(data):
        if not isinstance(article, dict):
            raise DataQualityError(f"{index}번 뉴스가 딕셔너리 형식이 아닙니다.")

        for field in required_fields:
            value = article.get(field)
            if not isinstance(value, str) or not value.strip():
                raise DataQualityError(
                    f"{index}번 뉴스의 {field} 필드가 없거나 비어 있습니다."
                )

    print(f"News Validation Success : {len(data)} articles")


def validate_stock_payload(records: list[dict[str, Any]]) -> None:
    """시세 레코드가 RAG·분석용 최소 필드를 갖췄는지 확인한다."""
    if not isinstance(records, list) or not records:
        raise DataQualityError("시세 수집 결과가 비어 있습니다.")

    required_text = ("symbol", "name", "date", "collected_at")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise DataQualityError(f"{index}번 시세 레코드가 딕셔너리가 아닙니다.")
        for field in required_text:
            if not isinstance(record.get(field), str) or not record[field].strip():
                raise DataQualityError(f"{index}번 시세의 {field} 필드가 비어 있습니다.")
        if not isinstance(record.get("close"), (int, float)):
            raise DataQualityError(f"{index}번 시세의 close 필드가 숫자가 아닙니다.")
