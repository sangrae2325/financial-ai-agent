"""금융 뉴스 RAG를 위한 리서치 대시보드형 Streamlit UI."""

from __future__ import annotations

import json
import sys
from uuid import uuid4
from pathlib import Path
from typing import Any

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import GEMINI_API_KEY, LOG_COLLECTOR_URL  # noqa: E402
from app.event_logger import send_event  # noqa: E402
from rag.financial_rag import run_financial_rag  # noqa: E402


CHROMA_PATH = PROJECT_ROOT / "data" / "chroma"
NEWS_PATH = PROJECT_ROOT / "data" / "news" / "news.json"

SUGGESTED_QUERIES = (
    "중동 리스크가 코스피와 유가에 미친 영향은?",
    "SK하이닉스 ADR 관련 뉴스 요약해줘",
    "최근 반도체 ETF가 오른 이유는?",
)
DEFAULT_TOP_K = 5


def main() -> None:
    """RAG 검색과 근거 확인에 집중한 단일 페이지 대시보드를 렌더링한다."""
    st.set_page_config(
        page_title="금융 뉴스 RAG Agent",
        page_icon="◈",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _inject_styles()
    _initialize_state()

    article_count = _load_article_count()
    _log_initial_events(article_count)
    _render_header(article_count)
    # UI에서는 전체 뉴스 범위를 기본으로 검색한다.
    press: str | None = None
    published_after: str | None = None

    left_column, right_column = st.columns([1.9, 1], gap="large")
    with left_column:
        question, run_requested = _render_question_panel()
        if run_requested:
            _run_query(
                question,
                top_k=DEFAULT_TOP_K,
                press=press,
                published_after=published_after,
            )
        _render_analysis()

    with right_column:
        _render_evidence_panel()


def _initialize_state() -> None:
    """추천 질문과 검색 결과를 rerun 사이에 유지한다."""
    st.session_state.setdefault("question", "")
    st.session_state.setdefault("rag_result", None)
    st.session_state.setdefault("last_error", None)
    st.session_state.setdefault("analytics_session_id", str(uuid4()))
    st.session_state.setdefault("page_view_logged", False)
    st.session_state.setdefault("data_loaded_logged", False)


def _render_header(article_count: int) -> None:
    st.markdown(
        """
        <div class="top-header">
          <div>
            <div class="page-title">금융 뉴스 RAG Agent</div>
            <div class="page-subtitle">최신 금융 뉴스를 근거로 답변합니다</div>
          </div>
          <div class="header-status"><span class="status-dot"></span> INDEX ONLINE &nbsp; · &nbsp; 뉴스 %s건</div>
        </div>
        """ % article_count,
        unsafe_allow_html=True,
    )


def _log_initial_events(article_count: int) -> None:
    """화면을 처음 연 세션에만 익명 진입·데이터 준비 이벤트를 남긴다."""
    session_id = str(st.session_state.analytics_session_id)
    if not st.session_state.page_view_logged:
        st.session_state.page_view_logged = send_event(
            collector_url=LOG_COLLECTOR_URL,
            event_type="page_view",
            session_id=session_id,
            properties={"article_count": article_count},
        )
    if not st.session_state.data_loaded_logged:
        st.session_state.data_loaded_logged = send_event(
            collector_url=LOG_COLLECTOR_URL,
            event_type="data_loaded",
            session_id=session_id,
            properties={"article_count": article_count},
        )


def _render_question_panel() -> tuple[str, bool]:
    st.markdown('<div class="panel-label">AI MARKET RESEARCH</div>', unsafe_allow_html=True)
    question = st.text_area(
        "분석하고 싶은 금융 이슈를 입력하세요",
        key="question",
        height=120,
        placeholder="예: 최근 엔화 환율 변동이 수출주에 미치는 영향",
        label_visibility="collapsed",
    )

    suggestion_area, action_column = st.columns([3, 1], vertical_alignment="bottom")
    with suggestion_area:
        suggestion_columns = st.columns(3)
        for column, suggested_query in zip(suggestion_columns, SUGGESTED_QUERIES, strict=True):
            with column:
                st.button(
                    suggested_query,
                    key=f"suggestion_{suggested_query}",
                    on_click=_set_question,
                    args=(suggested_query,),
                    use_container_width=False,
                )
    with action_column:
        run_requested = st.button(
            "✦  뉴스 검색 및 답변 생성",
            type="primary",
            use_container_width=True,
        )
    return question, run_requested


def _set_question(question: str) -> None:
    st.session_state.question = question


def _run_query(
    question: str,
    *,
    top_k: int,
    press: str | None,
    published_after: str | None,
) -> None:
    """버튼 클릭 시에만 Gemini와 ChromaDB를 호출한다."""
    if not question.strip():
        st.session_state.last_error = "분석할 금융 질문을 입력해 주세요."
        return
    if not GEMINI_API_KEY:
        st.session_state.last_error = "GEMINI_API_KEY가 없습니다. 프로젝트 루트의 .env를 확인하세요."
        return

    st.session_state.last_error = None
    try:
        with st.spinner("질문 해석 · 뉴스 검색 · 근거 기반 리포트 생성 중..."):
            st.session_state.rag_result = run_financial_rag(
                question,
                chroma_path=CHROMA_PATH,
                top_k=top_k,
                press=press,
                published_after=published_after,
            )
        result = st.session_state.rag_result
        send_event(
            collector_url=LOG_COLLECTOR_URL,
            event_type="record_search",
            session_id=str(st.session_state.analytics_session_id),
            properties={
                "query_length": len(question),
                "result_count": int(result["search_result"]["hit_count"]),
                "keyword_count": len(result["search_plan"]["keywords"]),
            },
        )
    except Exception as exc:
        st.session_state.last_error = f"실행 중 오류가 발생했습니다: {exc}"
        send_event(
            collector_url=LOG_COLLECTOR_URL,
            event_type="client_error",
            session_id=str(st.session_state.analytics_session_id),
            properties={"stage": "rag_query"},
        )


def _render_analysis() -> None:
    error = st.session_state.last_error
    result = st.session_state.rag_result
    if error:
        st.error(error)
        return
    if not result:
        st.markdown(
            """
            <div class="empty-state">
              <div class="empty-icon">◈</div>
              <b>금융 이슈를 입력해 리서치를 시작하세요.</b><br/>
              <span>AI가 검색 계획을 만들고, ChromaDB의 뉴스 근거를 바탕으로 답변합니다.</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    _render_search_plan(result)
    _render_market_snapshot(result["market_data"], result.get("exchange_data"))
    st.markdown('<div class="report-heading">◈ &nbsp; AI 분석 리포트</div>', unsafe_allow_html=True)
    st.markdown('<div class="report-card">', unsafe_allow_html=True)
    st.write(result["answer"])
    st.markdown(
        "<div class='disclaimer'>* 본 분석은 검색된 뉴스 기사를 바탕으로 AI가 요약한 결과이며, 투자 조언이 아닙니다.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)


def _render_market_snapshot(
    quotes: list[dict[str, Any]], exchange_rate: dict[str, Any] | None
) -> None:
    """질문에서 인식한 종목·환율의 저장된 최신 시장 데이터를 표시한다."""
    if not quotes and not exchange_rate:
        return
    st.markdown('<div class="market-title">MARKET SNAPSHOT</div>', unsafe_allow_html=True)
    cards: list[tuple[str, dict[str, Any]]] = [("stock", quote) for quote in quotes]
    if exchange_rate:
        cards.append(("exchange", exchange_rate))
    columns = st.columns(min(len(cards), 3))
    for column, (card_type, data) in zip(columns, cards, strict=False):
        if card_type == "exchange":
            with column:
                st.markdown(
                    f"""
                    <div class="market-card">
                      <div class="market-name">USD/KRW 환율</div>
                      <div class="market-price">{float(data['rate']):,.2f}</div>
                      <div class="market-change">1 USD당 KRW</div>
                      <div class="market-date">기준 {data.get('updated_at', '알 수 없음')}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            continue
        quote = data
        change = float(quote.get("change") or 0)
        change_pct = quote.get("change_pct")
        sign = "+" if change > 0 else ""
        percent = f"{sign}{float(change_pct):.2f}%" if isinstance(change_pct, (int, float)) else "변동률 없음"
        with column:
            st.markdown(
                f"""
                <div class="market-card">
                  <div class="market-name">{quote.get('name', '종목')}</div>
                  <div class="market-price">{float(quote['close']):,.0f}원</div>
                  <div class="market-change">{sign}{change:,.0f}원 · {percent}</div>
                  <div class="market-date">수집일 {quote.get('date', '알 수 없음')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_search_plan(result: dict[str, Any]) -> None:
    plan = result["search_plan"]
    filters = result["applied_filters"]
    with st.expander("⌘  SEARCH STRATEGY & PLAN", expanded=True):
        first, second = st.columns(2)
        with first:
            st.caption("SEMANTIC QUERY")
            st.code(plan["semantic_query"], language=None)
            st.caption("KEYWORDS")
            keywords = plan["keywords"] or ["추출된 키워드 없음"]
            st.markdown(" ".join(f"`{keyword}`" for keyword in keywords))
        with second:
            st.markdown(
                f"""
                <div class="retrieval-card">
                  <div class="metric-label">RETRIEVAL METRICS</div>
                  <div class="metric-value">{result['search_result']['hit_count']}건 <span>검색 청크</span></div>
                  <div class="metric-label filter-label">APPLIED FILTERS</div>
                  <div class="filter-value">언론사: {filters['press'] or '전체'}<br/>
                  시작일: {filters['published_after'] or '전체 기간'}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_evidence_panel() -> None:
    result = st.session_state.rag_result
    st.markdown('<div class="evidence-title">CITATIONS & EVIDENCE</div>', unsafe_allow_html=True)
    # 고정 높이 컨테이너: 근거가 많아도 우측 패널 안에서만 스크롤한다.
    # 일반적인 AI 분석 리포트 높이와 맞춰 근거를 더 많이 노출한다.
    # 이 높이를 넘는 기사만 패널 내부에서 스크롤된다.
    with st.container(height=840, border=False):
        if not result:
            st.info("답변을 생성하면 여기에서 실제 검색 근거를 확인할 수 있습니다.")
            return

        hits = result["search_result"]["hits"]
        if not hits:
            st.warning("현재 필터 조건에 맞는 근거 뉴스가 없습니다.")
            return

        for number, hit in enumerate(hits, start=1):
            metadata = hit["metadata"]
            hybrid_score = float(hit.get("hybrid_score", max(0.0, 1 - float(hit["distance"]))))
            with st.container(border=True):
                top_left, top_right = st.columns([1, 1])
                with top_left:
                    st.markdown(f"<span class='evidence-badge'>근거 {number}</span>", unsafe_allow_html=True)
                with top_right:
                    st.markdown(
                        f"<div class='similarity'>Hybrid: {hybrid_score:.2f}</div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(f"<div class='source-title'>{metadata.get('title', '제목 없음')}</div>", unsafe_allow_html=True)
                st.caption(
                    f"{metadata.get('press', '알 수 없음')} · "
                    f"{metadata.get('published_date', metadata.get('published_at', '날짜 없음'))}"
                )
                st.write(_shorten(hit["text"], 230))
                url = metadata.get("url")
                if url:
                    st.link_button("원문 열기 ↗", url, use_container_width=True)


def _load_article_count() -> int:
    return len(_load_articles())


def _load_articles() -> list[dict[str, Any]]:
    if not NEWS_PATH.exists():
        return []
    try:
        with NEWS_PATH.open(encoding="utf-8") as file:
            payload = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def _inject_styles() -> None:
    """디자인 시안의 네이비 사이드바·리서치 패널 분위기를 적용한다."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap');
        :root { --navy:#131b2e; --blue:#2170e4; --surface:#f7f9fb; --border:#c6c6cd; --text:#191c1e; }
        /* Streamlit의 기본 상단 툴바가 대시보드 헤더를 가리지 않게 한다. */
        [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
        [data-testid="stSidebarHeader"] { display:none !important; }
        [data-testid="stAppViewContainer"] { padding-top:0; }
        .stApp { background:var(--surface); font-family:'Inter', sans-serif; color:var(--text); }
        .block-container { max-width:1550px; padding:1.5rem 2rem 2.5rem; }
        .top-header { background:white; border:1px solid var(--border); border-radius:8px; padding:1rem 1.25rem; margin-bottom:1.25rem; display:flex; justify-content:space-between; align-items:center; }
        .page-title { color:#131b2e; font-size:20px; font-weight:800; } .page-subtitle { color:#60636a; font-size:12px; margin-top:2px; }
        .header-status { color:#566078; font:500 11px 'JetBrains Mono', monospace; } .status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:#16a34a; }
        .panel-label, .evidence-title { color:#60636a; font-size:11px; font-weight:800; letter-spacing:1px; margin:.2rem 0 .55rem; }
        [data-testid="stTextArea"] textarea { background:white; border:1px solid var(--border); border-radius:8px; font-size:16px; padding:1rem; }
        [data-testid="stTextArea"] textarea { color:#172033 !important; caret-color:#172033; }
        [data-testid="stTextArea"] textarea::placeholder { color:#64748b !important; opacity:1; }
        [data-testid="stTextArea"] textarea:focus { border-color:var(--blue); box-shadow:0 0 0 1px var(--blue); }
        div[data-testid="stButton"] > button { border-radius:7px; font-size:12px; font-weight:700; min-height:2.45rem; }
        div[data-testid="stButton"] > button[kind="primary"] { background:var(--navy); border-color:var(--navy); color:white; }
        div[data-testid="stButton"] > button[kind="primary"] * { color:white !important; }
        div[data-testid="stButton"] > button[kind="secondary"] { background:white; border-color:var(--border); color:#45464d; white-space:normal; height:100%; }
        .empty-state { background:white; border:1px dashed var(--border); border-radius:8px; padding:4rem 2rem; text-align:center; color:#60636a; margin-top:1.5rem; line-height:1.8; }
        .empty-icon { color:var(--blue); font-size:28px; margin-bottom:.5rem; }
        .report-heading { color:#131b2e; font-size:18px; font-weight:800; margin:1.6rem 0 .75rem; }
        .market-title { color:#60636a; font-size:11px; font-weight:800; letter-spacing:1px; margin:1.2rem 0 .55rem; }
        .market-card { background:#f0f5ff; border:1px solid #adc6ff; border-radius:7px; padding:.8rem .95rem; }
        .market-name { color:#45464d; font-size:12px; font-weight:800; }
        .market-price { color:#131b2e; font:700 20px 'JetBrains Mono', monospace; margin:.3rem 0; }
        .market-change { color:#0058be; font-size:12px; font-weight:700; }
        .market-date { color:#76777d; font-size:10px; margin-top:.35rem; }
        .report-card { background:white; border:1px solid var(--border); border-radius:8px; padding:1.25rem 1.4rem; line-height:1.8; }
        .disclaimer { border-top:1px solid var(--border); color:#76777d; font-size:11px; font-style:italic; margin-top:1.5rem; padding-top:.8rem; }
        [data-testid="stExpander"] { background:#eceef0; border:1px solid var(--border); border-radius:7px; }
        .retrieval-card { background:white; border:1px solid #e0e3e5; border-radius:5px; min-height:116px; padding:.8rem .9rem; }
        .metric-label { color:#76777d; font-size:10px; font-weight:800; letter-spacing:.7px; }
        .metric-value { color:#0058be; font:700 22px 'JetBrains Mono', monospace; margin:.25rem 0 .75rem; }
        .metric-value span { color:#45464d; font:500 11px 'Inter', sans-serif; }
        .filter-label { border-top:1px solid #e0e3e5; padding-top:.65rem; }
        .filter-value { color:#45464d; font-size:11px; line-height:1.6; margin-top:.25rem; }
        .evidence-badge { color:#0058be; background:#e8f0ff; font-size:10px; font-weight:800; padding:.2rem .45rem; border-radius:3px; }
        .similarity { color:#15803d; text-align:right; font:500 11px 'JetBrains Mono', monospace; }
        .source-title { color:#131b2e; font-size:14px; font-weight:800; line-height:1.35; margin:.75rem 0 .3rem; }
        [data-testid="stLinkButton"] a { color:#0058be; border-color:#adc6ff; font-size:12px; font-weight:700; }
        /* 카드 배경은 밝게 고정했으므로 라이트 테마의 기본 흐린 글자색을 덮어쓴다. */
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] li,
        [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] div,
        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"],
        [data-testid="stAppViewContainer"] [data-testid="stExpander"] summary,
        [data-testid="stAppViewContainer"] [data-testid="stAlert"] p { color:#1f2937; }
        [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] { color:#4b5563 !important; }
        /* 위의 본문 규칙이 버튼 안쪽 레이블까지 바꾸지 않도록 다시 지정한다. */
        div[data-testid="stButton"] > button[kind="primary"] [data-testid="stMarkdownContainer"] p { color:white !important; }
        @media (max-width: 900px) { .block-container { padding:1rem; } .top-header { display:block; } .header-status { margin-top:.65rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
