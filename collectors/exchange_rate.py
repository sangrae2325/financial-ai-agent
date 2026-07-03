"""
환율 데이터 수집기

기능
- 환율 API 호출
- JSON 데이터 반환
"""

from typing import Any

import requests

API_URL = "https://open.er-api.com/v6/latest/USD"

def fetch_exchange_rate(timeout: int = 10) -> dict[str, Any]:
    """
    환율 API에서 최신 환율 데이터를 가져온다.

    Args:
        timeout: 요청 제한 시간(초)

    Returns:
        환율 정보(JSON)
    """

    response = requests.get(API_URL, timeout=timeout)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict):
        raise ValueError("API 응답 형식이 올바르지 않습니다.")
    return data