"""네이버 금융에서 국내 핵심 종목의 최신 시세를 수집한다."""

from __future__ import annotations

import re
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup


NAVER_STOCK_URL = "https://finance.naver.com/item/main.naver?code={symbol}"
DEFAULT_UNIVERSE_PATH = Path(__file__).resolve().parents[1] / "data" / "config" / "stock_universe.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; financial-ai-agent/1.0)"}


def fetch_stock_prices(
    symbols: dict[str, str] | None = None,
    *,
    timeout: int = 15,
    session: Any = requests,
) -> list[dict[str, Any]]:
    """종목별 최신 종가·등락폭·등락률을 수집한다.

    네이버 금융 HTML을 프로젝트 공통 스키마로 변환할 뿐, 저장·임베딩은 하지
    않는다. ``session`` 주입은 네트워크 없이 단위 테스트하기 위해 둔다.
    """
    target_symbols = symbols or load_stock_universe()
    records: list[dict[str, Any]] = []
    for symbol, name in target_symbols.items():
        response = session.get(
            NAVER_STOCK_URL.format(symbol=symbol),
            headers=HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
        records.append(_parse_stock_page(response.text, symbol=symbol, name=name))
    return records


def fetch_stock(timeout: int = 15) -> list[dict[str, Any]]:
    """프로젝트 초기 설계의 Collector 이름을 유지한 기본 시세 수집 함수다."""
    return fetch_stock_prices(timeout=timeout)


def load_stock_universe(path: str | Path = DEFAULT_UNIVERSE_PATH) -> dict[str, str]:
    """수집 대상 종목 목록을 JSON 설정 파일에서 읽는다.

    종목 추가는 Collector 코드를 수정하는 대신 ``stock_universe.json``에
    ``종목코드: 종목명`` 한 줄을 추가하는 방식으로 한다.
    """
    with Path(path).open(encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict) or not payload:
        raise ValueError("종목 유니버스 설정은 비어 있지 않은 JSON 객체여야 합니다.")
    if not all(isinstance(code, str) and isinstance(name, str) for code, name in payload.items()):
        raise ValueError("종목 유니버스는 '종목코드: 종목명' 형태여야 합니다.")
    return payload


def _parse_stock_page(html: str, *, symbol: str, name: str) -> dict[str, Any]:
    """네이버 금융 종목 페이지에서 최신 시세 정보만 추출한다."""
    soup = BeautifulSoup(html, "html.parser")
    close_node = soup.select_one(".no_today .blind")
    if close_node is None:
        raise ValueError(f"현재가를 찾을 수 없습니다: {symbol}")
    close = _parse_number(close_node.get_text())

    change_nodes = soup.select(".no_exday .blind")
    change_texts = [node.get_text(strip=True) for node in change_nodes]
    direction = next((value for value in change_texts if value in {"상승", "하락", "보합"}), "보합")
    numeric_values = [_parse_number(value) for value in change_texts if _contains_number(value)]
    raw_change = numeric_values[0] if numeric_values else 0.0
    change = -raw_change if direction == "하락" else raw_change
    change_pct = numeric_values[1] if len(numeric_values) > 1 else None
    if change_pct is not None and direction == "하락":
        change_pct = -change_pct

    collected_at = datetime.now(timezone.utc)
    return {
        "symbol": symbol,
        "name": name,
        "date": collected_at.date().isoformat(),
        "close": close,
        "change": change,
        "change_pct": change_pct,
        "collected_at": collected_at.isoformat(),
    }


def _contains_number(value: str) -> bool:
    return bool(re.search(r"\d", value))


def _parse_number(value: str) -> float:
    normalized = re.sub(r"[^0-9.]", "", value)
    if not normalized:
        raise ValueError(f"숫자로 변환할 수 없는 시세 값입니다: {value}")
    return float(normalized)
