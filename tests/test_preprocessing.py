"""뉴스 전처리 및 청킹 단위 테스트."""

import unittest

from preprocessing.chunk import chunk_news
from preprocessing.preprocess import normalize_news
from pipelines.news_pipeline import merge_news_articles


ARTICLE = {
    "title": "  반도체  뉴스  ",
    "content": "첫 번째 문장입니다.   두 번째 문장입니다. 세 번째 문장입니다.",
    "press": " 테스트경제 ",
    "published_at": " 2026-07-12 10:00 ",
    "url": "https://example.com/news/1",
}


class PreprocessingTest(unittest.TestCase):
    """전처리 계층의 데이터 변환 규칙을 검증한다."""

    def test_normalize_news_removes_whitespace_and_duplicates(self) -> None:
        """공백을 정리하고 동일 URL 기사는 하나만 남긴다."""
        articles = normalize_news([ARTICLE, ARTICLE.copy()])

        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], "반도체 뉴스")
        self.assertEqual(articles[0]["content"], "첫 번째 문장입니다. 두 번째 문장입니다. 세 번째 문장입니다.")

    def test_chunk_news_preserves_metadata_and_overlap(self) -> None:
        """청크는 제목·메타데이터를 보존하며 본문 중복 구간을 가진다."""
        article = {**ARTICLE, "content": "abcdefghij"}
        chunks = chunk_news(normalize_news([article]), chunk_size=6, overlap=2)

        self.assertEqual(len(chunks), 3)
        self.assertIn("제목: 반도체 뉴스", chunks[0]["text"])
        self.assertEqual(chunks[0]["metadata"]["press"], "테스트경제")
        self.assertEqual(chunks[0]["metadata"]["published_date"], "2026-07-12")
        self.assertEqual(chunks[0]["metadata"]["published_date_key"], 20260712)
        self.assertIn("abcdef", chunks[0]["text"])
        self.assertIn("efghij", chunks[1]["text"])

    def test_chunk_news_rejects_invalid_overlap(self) -> None:
        """청크 길이 이상인 overlap은 무한 반복을 방지하기 위해 거부한다."""
        with self.assertRaises(ValueError):
            chunk_news(normalize_news([ARTICLE]), chunk_size=10, overlap=10)

    def test_merge_news_articles_accumulates_and_prefers_new_article(self) -> None:
        """매일 수집한 기사는 기존 목록에 누적하고 같은 URL은 새 기사로 갱신한다."""
        existing = [ARTICLE]
        updated = {**ARTICLE, "title": "새 제목", "content": "새 본문입니다."}
        another = {
            **ARTICLE,
            "title": "다른 기사",
            "content": "다른 본문입니다.",
            "url": "https://example.com/news/2",
        }

        merged = merge_news_articles([updated, another], existing)

        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0]["title"], "새 제목")
        self.assertEqual(merged[1]["url"], "https://example.com/news/2")
