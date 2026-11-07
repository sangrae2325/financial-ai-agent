"""금융 AI Agent의 익명 행동 이벤트를 Cloud Logging에 남기는 FastAPI 서비스."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "")
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "").rstrip("/")


class EventType(str, Enum):
    """금융 UI가 기록할 수 있는 익명 이벤트 종류다."""

    PAGE_VIEW = "page_view"
    DATA_LOADED = "data_loaded"
    RECORD_SEARCH = "record_search"
    RECORD_OPEN = "record_open"
    CLIENT_ERROR = "client_error"


Scalar = str | int | float | bool | None


class EventRequest(BaseModel):
    """개인정보를 포함하지 않는 최소 행동 이벤트 스키마다."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    session_id: Annotated[str, Field(min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")]
    page: Annotated[str, Field(min_length=1, max_length=100)]
    properties: dict[str, Scalar] = Field(default_factory=dict, max_length=10)
    occurred_at: datetime | None = None

    @field_validator("properties")
    @classmethod
    def validate_properties(cls, value: dict[str, Scalar]) -> dict[str, Scalar]:
        """질문 원문·개인정보처럼 기록하면 안 되는 속성을 차단한다."""
        blocked = {"name", "email", "phone", "password", "token", "authorization", "body", "query"}
        for key, item in value.items():
            normalized_key = key.strip().lower()
            if not normalized_key or len(key) > 40:
                raise ValueError("properties key는 1~40자여야 합니다.")
            if normalized_key in blocked:
                raise ValueError(f"개인정보 또는 자유 입력 필드는 수집할 수 없습니다: {key}")
            if isinstance(item, str) and len(item) > 120:
                raise ValueError("properties 문자열 값은 120자 이하여야 합니다.")
        return value


app = FastAPI(
    title="Financial AI Agent Event Collector",
    version="1.0.0",
    description="금융 RAG UI의 익명 행동 이벤트를 구조화 로그로 기록합니다.",
)

if ALLOWED_ORIGIN:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[ALLOWED_ORIGIN],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=3600,
    )


@app.get("/health")
def health() -> dict[str, str]:
    """Cloud Run과 배포 후 검증에 쓰는 상태 확인 엔드포인트다."""
    return {"status": "ok", "service": "financial-agent-event-collector"}


@app.post("/events", status_code=202)
def collect_event(
    event: EventRequest,
    x_cloud_trace_context: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """JSON 한 줄을 stdout으로 출력해 Cloud Logging이 구조화 로그로 수집하게 한다."""
    event_id = str(uuid4())
    received_at = datetime.now(timezone.utc)
    entry: dict[str, object] = {
        "severity": "INFO",
        "message": f"frontend_event:{event.event_type.value}",
        "service": "financial-agent-event-collector",
        "event_id": event_id,
        "event_type": event.event_type.value,
        "session_id": event.session_id,
        "page": event.page,
        "properties": event.properties,
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
        "received_at": received_at.isoformat(),
    }
    if x_cloud_trace_context and PROJECT_ID:
        trace_id = x_cloud_trace_context.split("/", 1)[0]
        entry["logging.googleapis.com/trace"] = f"projects/{PROJECT_ID}/traces/{trace_id}"

    print(json.dumps(entry, ensure_ascii=False, separators=(",", ":")), file=sys.stdout, flush=True)
    return {"status": "accepted", "event_id": event_id}
