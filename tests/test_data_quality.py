"""데이터 품질 검증 단위 테스트."""

import unittest

from validation.data_quality import (
    DataQualityError,
    validate_news_payload,
    validate_stock_payload,
)


VALID_ARTICLE = {
    "title": "테스트 기사",
    "content": "테스트 본문",
    "press": "테스트언론사",
    "published_at": "2026-07-10 10:00",
    "url": "https://example.com/article",
}


class NewsDataQualityTest(unittest.TestCase):
    """뉴스 데이터 품질 규칙 테스트."""

    def test_validate_news_payload_accepts_complete_articles(self) -> None:
        """필수 필드가 채워진 기사 목록을 통과시킨다."""
        validate_news_payload([VALID_ARTICLE])

    def test_validate_news_payload_rejects_empty_content(self) -> None:
        """본문이 비어 있는 기사를 거부한다."""
        invalid_article = {**VALID_ARTICLE, "content": "   "}

        with self.assertRaises(DataQualityError):
            validate_news_payload([invalid_article])

    def test_validate_news_payload_rejects_empty_list(self) -> None:
        """수집 결과가 없는 경우를 거부한다."""
        with self.assertRaises(DataQualityError):
            validate_news_payload([])

    def test_validate_stock_payload_accepts_quote(self) -> None:
        """종목·날짜·종가를 가진 시세 레코드를 통과시킨다."""
        validate_stock_payload(
            [
                {
                    "symbol": "005930.KS",
                    "name": "삼성전자",
                    "date": "2026-07-26",
                    "close": 100000.0,
                    "collected_at": "2026-07-26T10:00:00+00:00",
                }
            ]
        )
