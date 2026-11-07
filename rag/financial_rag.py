"""금융 뉴스 검색 결과를 근거 기반 Gemini 답변으로 연결한다."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import GEMINI_API_KEY, GEMINI_MODEL
from rag.financial_query_parser import FinancialSearchPlan, create_financial_search_plan
from rag.market_context import (
    build_market_context,
    find_relevant_exchange_rate,
    find_relevant_stock_quotes,
)
from vectorstore.chroma import DEFAULT_COLLECTION, search_news


def build_news_context(search_result: dict[str, Any]) -> str:
    """Chroma 검색 결과를 출처가 있는 RAG 컨텍스트 문자열로 변환한다."""
    hits = search_result.get("hits", [])
    if not hits:
        return "관련 뉴스를 찾지 못했습니다."

    sections: list[str] = []
    for index, hit in enumerate(hits, start=1):
        metadata = hit["metadata"]
        sections.append(
            "\n".join(
                [
                    f"[근거 {index}] {metadata.get('title', '제목 없음')}",
                    f"언론사: {metadata.get('press', '알 수 없음')}",
                    f"발행: {metadata.get('published_at', '알 수 없음')}",
                    f"URL: {metadata.get('url', '알 수 없음')}",
                    f"내용: {hit['text']}",
                ]
            )
        )
    return "\n\n".join(sections)


def run_financial_rag(
    question: str,
    *,
    chroma_path: str | Path,
    top_k: int = 5,
    press: str | None = None,
    published_after: str | None = None,
    collection_name: str = DEFAULT_COLLECTION,
    api_key: str | None = None,
    model_name: str | None = None,
    stock_path: str | Path | None = None,
    exchange_path: str | Path | None = None,
) -> dict[str, Any]:
    """질문 해석, Chroma 검색, Gemini 답변 생성을 한 번에 수행한다.

    UI의 수동 필터가 있으면 모델이 만든 필터보다 우선한다. 답변 모델에는 검색된
    뉴스 컨텍스트만 전달해, 제공되지 않은 사실을 단정하지 않도록 지시한다.
    """
    plan = create_financial_search_plan(
        question,
        api_key=api_key,
        model_name=model_name,
    )
    applied_press = press if press is not None else plan.press
    applied_published_after = (
        published_after if published_after is not None else plan.published_after
    )
    search_result = search_news(
        plan.semantic_query,
        chroma_path=chroma_path,
        collection_name=collection_name,
        top_k=top_k,
        keywords=plan.keywords,
        press=applied_press,
        published_after=applied_published_after,
    )
    context = build_news_context(search_result)
    market_data = find_relevant_stock_quotes(
        question,
        **({"stock_path": stock_path} if stock_path is not None else {}),
    )
    exchange_data = find_relevant_exchange_rate(
        question,
        **({"exchange_path": exchange_path} if exchange_path is not None else {}),
    )
    market_context = build_market_context(market_data, exchange_data)
    if not search_result["hits"] and not market_data and not exchange_data:
        answer = "적용한 조건에 맞는 뉴스 청크를 찾지 못했습니다. 필터를 완화해 다시 검색해 보세요."
    else:
        answer = generate_grounded_answer(
            question,
            context,
            market_context=market_context,
            api_key=api_key,
            model_name=model_name,
        )

    return {
        "question": question,
        "search_plan": plan.to_dict(),
        "applied_filters": {
            "press": applied_press,
            "published_after": applied_published_after,
        },
        "search_result": search_result,
        "market_data": market_data,
        "exchange_data": exchange_data,
        "answer": answer,
    }


def generate_grounded_answer(
    question: str,
    context: str,
    *,
    market_context: str = "질문에서 직접 언급된 종목의 저장된 시세 데이터가 없습니다.",
    api_key: str | None = None,
    model_name: str | None = None,
) -> str:
    """검색 컨텍스트에 있는 내용만 이용해 금융 질문에 답한다."""
    resolved_key = api_key or GEMINI_API_KEY
    if not resolved_key:
        raise ValueError("GEMINI_API_KEY가 없습니다. .env에 키를 설정하세요.")

    prompt = f"""당신은 금융 뉴스 RAG 답변 도우미입니다.
    반드시 아래 [근거 N]과 [시장 데이터]에 포함된 정보만 사용하세요. 근거에 없는
사실, 최신 시세, 투자 판단은 만들지 마세요. 충분한 근거가 없으면 그 사실을 명확히 말하세요.
핵심을 3~5문장으로 한국어로 설명하고, 각 문장 또는 문단 끝에 [근거 N] 형식으로
출처 번호를 표시하세요. 시세 수치를 언급할 때는 [시장 데이터]를 표시하세요.
이는 투자 조언이 아님을 필요할 때만 짧게 덧붙이세요.

질문: {question}

검색 근거:
{context}

시장 시세 근거:
{market_context}
"""
    try:
        from google import genai
    except ImportError as exc:
        raise ImportError("google-genai를 설치하세요: pip install google-genai") from exc
    client = genai.Client(api_key=resolved_key)
    response = client.models.generate_content(
        model=model_name or GEMINI_MODEL,
        contents=prompt,
    )
    answer = (response.text or "").strip()
    if not answer:
        raise RuntimeError("Gemini가 빈 답변을 반환했습니다.")
    return answer
