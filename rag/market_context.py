"""질문에 언급된 시장 데이터를 RAG용 구조화된 근거로 만든다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_STOCK_PATH = Path(__file__).resolve().parents[1] / "data" / "stocks" / "stocks.json"
DEFAULT_EXCHANGE_PATH = Path(__file__).resolve().parents[1] / "data" / "exchange" / "exchange.json"


def find_relevant_stock_quotes(
    question: str, *, stock_path: str | Path = DEFAULT_STOCK_PATH
) -> list[dict[str, Any]]:
    """질문에 종목명 또는 종목 코드가 있으면 해당 종목의 최신 레코드를 반환한다."""
    records = _load_stock_records(stock_path)
    latest_by_symbol: dict[str, dict[str, Any]] = {}
    for record in records:
        symbol = record.get("symbol")
        if not isinstance(symbol, str):
            continue
        previous = latest_by_symbol.get(symbol)
        if previous is None or _record_time(record) > _record_time(previous):
            latest_by_symbol[symbol] = record

    normalized_question = question.lower()
    return [
        record
        for record in latest_by_symbol.values()
        if str(record.get("name", "")).lower() in normalized_question
        or str(record.get("symbol", "")) in question
    ]


def find_relevant_exchange_rate(
    question: str, *, exchange_path: str | Path = DEFAULT_EXCHANGE_PATH
) -> dict[str, Any] | None:
    """환율 질문이면 저장된 USD/KRW 환율을 구조화해 반환한다.

    현재 수집기는 USD를 기준 통화로 사용하므로 ``rates["KRW"]``는
    '1 USD당 KRW' 값이다. 환율과 무관한 질문에는 데이터를 억지로 넣지 않는다.
    """
    normalized_question = question.lower().replace(" ", "")
    exchange_keywords = ("환율", "원달러", "원/달러", "usd/krw", "외환")
    if not any(keyword in normalized_question for keyword in exchange_keywords):
        return None

    path = Path(exchange_path)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    rates = payload.get("rates")
    rate = rates.get("KRW") if isinstance(rates, dict) else None
    if payload.get("base_code") != "USD" or not isinstance(rate, (int, float)):
        return None
    return {
        "pair": "USD/KRW",
        "rate": float(rate),
        "base_code": "USD",
        "updated_at": payload.get("time_last_update_utc", "알 수 없음"),
    }


def build_market_context(
    quotes: list[dict[str, Any]], exchange_rate: dict[str, Any] | None = None
) -> str:
    """LLM 프롬프트에 넣을 출처 표기가 있는 시세 컨텍스트를 만든다."""
    if not quotes and not exchange_rate:
        return "질문에서 직접 언급된 종목의 저장된 시세 데이터가 없습니다."

    lines = ["[시장 데이터]"]
    for quote in quotes:
        change = float(quote.get("change") or 0)
        change_pct = quote.get("change_pct")
        sign = "+" if change > 0 else ""
        percent_text = (
            f" ({sign}{float(change_pct):.2f}%)" if isinstance(change_pct, (int, float)) else ""
        )
        lines.append(
            f"- {quote.get('name', '종목')} ({quote.get('symbol', '')}): "
            f"종가 {float(quote['close']):,.0f}원, 등락 {sign}{change:,.0f}원{percent_text}, "
            f"수집일 {quote.get('date', '알 수 없음')}"
        )
    if exchange_rate:
        lines.append(
            f"- USD/KRW: 1 USD = {float(exchange_rate['rate']):,.2f} KRW, "
            f"기준 시각 {exchange_rate.get('updated_at', '알 수 없음')}"
        )
    return "\n".join(lines)


def _load_stock_records(path: str | Path) -> list[dict[str, Any]]:
    resolved_path = Path(path)
    if not resolved_path.exists():
        return []
    try:
        with resolved_path.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return [record for record in payload if isinstance(record, dict)] if isinstance(payload, list) else []


def _record_time(record: dict[str, Any]) -> tuple[str, str]:
    return str(record.get("date", "")), str(record.get("collected_at", ""))
