"""
로컬 파일 저장 모듈

기능
- JSON 데이터를 로컬에 저장
"""

from pathlib import Path
from typing import Any
import json

def save_json(data: dict[str, Any], file_path: str) -> None:
    """
    JSON 데이터를 지정한 경로에 저장한다.
    
    Args:
        data: 저장할 JSON 데이터
        file_path: 저장 경로
    """

    path = Path(file_path)

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