"""Gemini 호출 없이 금융 RAG의 입력·출력 규칙을 검증한다."""

from __future__ import annotations

import unittest

from rag.financial_query_parser import _plan_from_payload
from rag.financial_rag import build_news_context


class FinancialRagTest(unittest.TestCase):
    def test_plan_keeps_only_valid_date_filter(self) -> None:
        """검색 계획의 날짜 필터는 YYYY-MM-DD일 때만 유지한다."""
        plan = _plan_from_payload(
            {
                "semantic_query": "반도체 투자 뉴스",
                "keywords": ["반도체", " 투자 "],
                "press": "서울경제",
                "published_after": "최근",
                "summary": "반도체 관련 기사를 찾습니다.",
            },
            fallback_query="원래 질문",
        )

        self.assertEqual(plan.semantic_query, "반도체 투자 뉴스")
        self.assertEqual(plan.keywords, ["반도체", "투자"])
        self.assertEqual(plan.press, "서울경제")
        self.assertIsNone(plan.published_after)

    def test_context_includes_source_number_and_metadata(self) -> None:
        """LLM에 주는 컨텍스트에는 근거 번호와 원문 정보가 포함된다."""
        context = build_news_context(
            {
                "hits": [
                    {
                        "text": "반도체 투자 관련 본문",
                        "metadata": {
                            "title": "반도체 뉴스",
                            "press": "서울경제",
                            "published_at": "2026-07-10",
                            "url": "https://example.com/news",
                        },
                    }
                ]
            }
        )

        self.assertIn("[근거 1] 반도체 뉴스", context)
        self.assertIn("언론사: 서울경제", context)
        self.assertIn("반도체 투자 관련 본문", context)


if __name__ == "__main__":
    unittest.main()
