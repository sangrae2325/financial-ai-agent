"""프로젝트 전반에서 사용하는 환경 설정이다.

비밀값은 코드에 작성하지 않고 프로젝트 루트의 .env 또는 터미널 환경 변수로
주입한다. GCP 설정은 기존 수집 파이프라인에서, Gemini 설정은 RAG 화면에서
사용한다.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # python-dotenv 설치 전에도 기존 GCP 파이프라인은 환경 변수만으로 동작한다.
    pass


PROJECT_ID = os.getenv("GCP_PROJECT_ID")

BUCKET_NAME = os.getenv("GCP_BUCKET")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# 신규 Gemini API 사용자도 사용할 수 있는 경량 Flash 모델을 기본값으로 쓴다.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

# 비어 있으면 UI 행동 로그 전송 기능은 비활성화된다.
LOG_COLLECTOR_URL = os.getenv("LOG_COLLECTOR_URL", "").rstrip("/")

DATASET = "financial_ai"

EXCHANGE_TABLE = "exchange_rates"
NEWS_TABLE = "financial_news"

METADATA_TABLE = "ingest_metadata"
