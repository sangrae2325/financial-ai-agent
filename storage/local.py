"""
로컬 파일 저장 모듈

기능
- JSON 데이터를 로컬에 저장
"""

from pathlib import Path
from typing import Any
import json


def save_json(data: Any, category: str) -> str:
    """
    JSON 데이터를 로컬에 저장한다.

    Args:
        data: 저장할 JSON 데이터(딕셔너리 또는 리스트)
        category: 데이터 종류 (exchange, news, stocks ...)

    Returns:
        저장된 파일 경로
    """

    path = Path(f"data/{category}/{category}.json")
    return save_json_to_path(data, path)


def save_json_to_path(data: Any, path: str | Path) -> str:
    """지정한 로컬 JSON 경로에 데이터를 저장한다.

    Storage 계층은 경로에 데이터를 쓰는 일만 수행한다. 날짜별 원본 보관이나
    누적 데이터 병합 같은 정책은 Pipeline 계층에서 결정한다.
    """
    path = Path(path)

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
