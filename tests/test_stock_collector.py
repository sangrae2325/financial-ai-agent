"""외부 네트워크 없이 주가 Collector의 응답 변환을 검증한다."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from collectors.stock import _parse_stock_page, fetch_stock_prices, load_stock_universe
from pipelines.stock_pipeline import merge_stock_records


HTML = """
<div class="no_today"><span class="blind">112,000</span></div>
<div class="no_exday">
  <span class="blind">상승</span><span class="blind">10,000</span><span class="blind">9.80%</span>
</div>
"""


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    text = HTML


class FakeSession:
    def get(self, *args, **kwargs):
        return FakeResponse()


class StockCollectorTest(unittest.TestCase):
    def test_fetch_stock_prices_returns_latest_quote(self) -> None:
        """여러 종목 응답을 프로젝트 공통 시세 스키마로 변환한다."""
        records = fetch_stock_prices({"005930": "삼성전자"}, session=FakeSession())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["symbol"], "005930")
        self.assertEqual(records[0]["close"], 112000.0)
        self.assertEqual(records[0]["change"], 10000.0)
        self.assertAlmostEqual(records[0]["change_pct"], 9.8)

    def test_merge_stock_records_prefers_new_quote(self) -> None:
        """같은 종목·거래일의 레코드는 새 수집 값으로 갱신한다."""
        old = {"symbol": "005930.KS", "date": "2026-07-25", "close": 100.0}
        new = {"symbol": "005930.KS", "date": "2026-07-25", "close": 110.0}

        merged = merge_stock_records([new], [old])

        self.assertEqual(merged, [new])

    def test_parse_latest_quote_rejects_missing_chart(self) -> None:
        """예상과 다른 API 응답은 Collector 단계에서 명확히 실패한다."""
        with self.assertRaises(ValueError):
            _parse_stock_page("<html></html>", symbol="005930", name="삼성전자")

    def test_load_stock_universe_reads_config_file(self) -> None:
        """종목 목록은 코드가 아닌 JSON 설정 파일에서 읽는다."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "universe.json"
            path.write_text(json.dumps({"005930": "삼성전자"}), encoding="utf-8")

            universe = load_stock_universe(path)

        self.assertEqual(universe, {"005930": "삼성전자"})
