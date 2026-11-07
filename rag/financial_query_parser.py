"""금융 질문을 벡터 검색용 질의와 metadata 필터로 해석한다."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL


@dataclass(frozen=True)
class FinancialSearchPlan:
    """벡터 검색에서 실제로 사용할 계획이다."""

    semantic_query: str
    keywords: list[str]
    press: str | None = None
    published_after: str | None = None
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """UI 및 JSON 출력용 일반 딕셔너리로 변환한다."""
        return asdict(self)


def create_financial_search_plan(
    question: str,
    *,
    api_key: str | None = None,
    model_name: str | None = None,
) -> FinancialSearchPlan:
    """Gemini로 질문을 해석한다. 키가 없으면 질문 자체를 검색어로 사용한다.

    모델은 사용자가 질문에 명시한 날짜와 언론사만 필터로 내보낼 수 있다.
    따라서 모델이 임의의 조건을 만들어 검색 대상을 좁히는 일을 막는다.
    """
    if not question.strip():
        raise ValueError("질문을 입력하세요.")

    resolved_key = api_key or GEMINI_API_KEY
    if not resolved_key:
        return FinancialSearchPlan(
            semantic_query=question.strip(),
            keywords=[],
            summary="API 키가 없어 질문 원문으로 검색했습니다.",
        )

    prompt = f"""당신은 금융 뉴스 RAG의 검색 계획 생성기입니다.
아래 사용자 질문을 검색 계획 JSON 하나로 변환하세요. JSON 이외의 문장은 쓰지 마세요.

반환 형식:
{{
  "semantic_query": "벡터 검색에 쓸 한국어 검색어",
  "keywords": ["핵심어"],
  "press": null 또는 "질문에 명시된 언론사명",
  "published_after": null 또는 "YYYY-MM-DD",
  "summary": "검색 전략 한 문장"
}}

규칙:
- press와 published_after는 질문에 직접 언급된 경우에만 사용합니다.
- 날짜는 정확한 YYYY-MM-DD로 판단할 수 있을 때만 사용하고, 상대 날짜(오늘/최근)는 null로 둡니다.
- 투자 조언을 만들지 말고 검색 의도만 표현합니다.

사용자 질문: {question.strip()}
"""
    client = _create_gemini_client(resolved_key)
    response = client.models.generate_content(
        model=model_name or GEMINI_MODEL,
        contents=prompt,
    )
    payload = _parse_json_response(response.text or "")
    return _plan_from_payload(payload, fallback_query=question)


def _plan_from_payload(payload: dict[str, Any], *, fallback_query: str) -> FinancialSearchPlan:
    """모델 JSON을 안전한 내부 검색 계획으로 정규화한다."""
    semantic_query = str(payload.get("semantic_query") or fallback_query).strip()
    raw_keywords = payload.get("keywords", [])
    keywords = (
        [str(keyword).strip() for keyword in raw_keywords if str(keyword).strip()]
        if isinstance(raw_keywords, list)
        else []
    )
    press = _optional_text(payload.get("press"))
    published_after = _optional_text(payload.get("published_after"))
    if published_after and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", published_after):
        published_after = None

    return FinancialSearchPlan(
        semantic_query=semantic_query,
        keywords=keywords,
        press=press,
        published_after=published_after,
        summary=str(payload.get("summary") or "질문의 핵심 의미로 뉴스를 검색합니다.").strip(),
    )


def _parse_json_response(text: str) -> dict[str, Any]:
    """코드 펜스가 섞인 Gemini 응답에서도 JSON 객체를 꺼낸다."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError("Gemini가 검색 계획 JSON을 올바르게 반환하지 않았습니다.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Gemini 검색 계획은 JSON 객체여야 합니다.")
    return payload


def _optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _create_gemini_client(api_key: str) -> Any:
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError("google-genai를 설치하세요: pip install google-genai") from exc
    return genai.Client(api_key=api_key)
