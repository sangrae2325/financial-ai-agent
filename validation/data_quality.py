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