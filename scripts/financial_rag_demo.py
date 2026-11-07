"""금융 뉴스 RAG를 터미널에서 실행하고 결과를 JSON으로 저장한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rag.financial_rag import run_financial_rag  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="금융 뉴스 ChromaDB RAG 데모")
    parser.add_argument("--query", required=True, help="금융 뉴스에 대한 자연어 질문")
    parser.add_argument("--top-k", type=int, default=3, help="가져올 뉴스 청크 수")
    parser.add_argument("--press", help="선택: 언론사 정확 일치 필터")
    parser.add_argument("--published-after", help="선택: YYYY-MM-DD 이후 기사 필터")
    parser.add_argument(
        "--chroma-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "chroma",
        help="ChromaDB 저장 경로",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "news" / "rag_answer.json",
        help="결과 JSON 저장 경로",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_financial_rag(
        args.query,
        chroma_path=args.chroma_path,
        top_k=args.top_k,
        press=args.press,
        published_after=args.published_after,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[완료] {result['search_result']['hit_count']}건 검색 -> {args.output}")
    print("\n[답변]")
    print(result["answer"])


if __name__ == "__main__":
    main()
