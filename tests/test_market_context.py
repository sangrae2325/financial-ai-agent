"""시세 JSON에서 질문 관련 종목의 구조화된 근거를 만드는 테스트."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rag.market_context import (
    build_market_context,
    find_relevant_exchange_rate,
    find_relevant_stock_quotes,
)


class MarketContextTest(unittest.TestCase):
    def test_find_relevant_stock_quotes_uses_latest_matching_record(self) -> None:
        """질문 종목과 일치하는 가장 최신 시세만 반환한다."""
        records = [
            {"symbol": "005930", "name": "삼성전자", "date": "2026-07-24", "close": 100000},
            {"symbol": "005930", "name": "삼성전자", "date": "2026-07-25", "close": 110000},
            {"symbol": "000660", "name": "SK하이닉스", "date": "2026-07-25", "close": 200000},
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stocks.json"
            path.write_text(json.dumps(records), encoding="utf-8")
            quotes = find_relevant_stock_quotes("오늘 삼성전자 주가", stock_path=path)

        self.assertEqual(len(quotes), 1)
        self.assertEqual(quotes[0]["close"], 110000)

    def test_build_market_context_marks_market_source(self) -> None:
        """LLM이 뉴스와 구분해 인용할 수 있게 시장 데이터 표기를 넣는다."""
        context = build_market_context(
            [{"symbol": "005930", "name": "삼성전자", "date": "2026-07-25", "close": 110000, "change": 1000, "change_pct": 0.92}]
        )

        self.assertIn("[시장 데이터]", context)
        self.assertIn("110,000원", context)

    def test_exchange_rate_is_added_only_for_exchange_question(self) -> None:
        """환율 질문에는 USD/KRW를 넣고, 종목 질문에는 넣지 않는다."""
        payload = {
            "base_code": "USD",
            "rates": {"KRW": 1500.5},
            "time_last_update_utc": "Fri, 24 Jul 2026 00:00:00 +0000",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "exchange.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            exchange = find_relevant_exchange_rate("원달러 환율을 알려줘", exchange_path=path)
            irrelevant = find_relevant_exchange_rate("삼성전자 주가", exchange_path=path)

        self.assertIsNotNone(exchange)
        self.assertEqual(exchange["rate"], 1500.5)
        self.assertIsNone(irrelevant)
        context = build_market_context([], exchange)
        self.assertIn("1 USD = 1,500.50 KRW", context)
