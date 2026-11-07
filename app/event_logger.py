"""금융 RAG UI의 익명 사용 이벤트를 로그 수집기로 전송한다."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def send_event(
    *,
    collector_url: str,
    event_type: str,
    session_id: str,
    properties: dict[str, str | int | float | bool | None] | None = None,
) -> bool:
    """익명 이벤트를 전송하고, 실패해도 RAG 기능은 계속 실행한다.

    호출부는 질문 원문·기사 본문·API 오류처럼 민감하거나 긴 값 대신 검색 길이,
    결과 수처럼 최소한의 집계 속성만 전달한다.
    """
    if not collector_url:
        return False

    payload = {
        "event_type": event_type,
        "session_id": session_id,
        "page": "financial-ai-agent",
        "properties": properties or {},
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    request = Request(
        f"{collector_url.rstrip('/')}/events",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=1.5) as response:
            return response.status == 202
    except (HTTPError, URLError, TimeoutError, OSError):
        return False
