"""
로컬 파일 저장 모듈

기능
- JSON 데이터를 로컬에 저장
"""

from pathlib import Path
from typing import Any
import json


def save_json(data: dict[str, Any], category: str) -> str:
    """
    JSON 데이터를 로컬에 저장한다.

    Args:
        data: 저장할 JSON 데이터
        category: 데이터 종류 (exchange, news, stocks ...)

    Returns:
        저장된 파일 경로
    """

    path = Path(f"data/{category}/{category}.json")

    # 폴더 없으면 자동 생성
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4,
        )

    print(f"Local Save Success : {path}")

    return str(path)