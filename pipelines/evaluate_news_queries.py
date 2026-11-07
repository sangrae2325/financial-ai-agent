"""금융 뉴스 질의 세트의 ChromaDB 검색 품질을 기록한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from embedding.news_embedding import DEFAULT_EMBEDDING_MODEL
from vectorstore.chroma import DEFAULT_COLLECTION, search_news


def evaluate_queries(
    queries: list[dict[str, Any]],
    *,
    chroma_path: Path,
    collection: str,
    model_name: str,
) -> dict[str, Any]:
    """질의별 관련 결과·필터 위반 여부를 계산한다."""
    results: list[dict[str, Any]] = []
    for item in queries:
        filters = item.get("filters", {})
        result = search_news(
            item["query"],
            chroma_path=chroma_path,
            collection_name=collection,
            model_name=model_name,
            top_k=int(item.get("top_k", 3)),
            press=filters.get("press"),
            published_after=filters.get("published_after"),
        )
        expected_terms = [term.lower() for term in item.get("expected_terms", [])]
        relevant_count = sum(
            _is_relevant(hit, expected_terms) for hit in result["hits"]
        )
        filter_violations = sum(
            not _matches_filters(hit["metadata"], filters) for hit in result["hits"]
        )
        results.append(
            {
                "id": item["id"],
                "query": item["query"],
                "filters": filters,
                "expected_terms": item.get("expected_terms", []),
                "purpose": item.get("purpose", ""),
                "hit_count": result["hit_count"],
                "relevant_count": relevant_count,
                "filter_violations": filter_violations,
                "hits": result["hits"],
            }
        )

    total = len(results)
    return {
        "summary": {
            "query_count": total,
            "hit_at_k": sum(item["relevant_count"] > 0 for item in results) / total if total else 0,
            "average_relevant_count": sum(item["relevant_count"] for item in results) / total if total else 0,
            "filter_violations": sum(item["filter_violations"] for item in results),
            "zero_hit_queries": sum(item["hit_count"] == 0 for item in results),
        },
        "results": results,
    }


def _is_relevant(hit: dict[str, Any], expected_terms: list[str]) -> bool:
    searchable = f"{hit['text']} {hit['metadata'].get('title', '')}".lower()
    return all(term in searchable for term in expected_terms)


def _matches_filters(metadata: dict[str, Any], filters: dict[str, str]) -> bool:
    press = filters.get("press")
    published_after = filters.get("published_after")
    if press and metadata.get("press") != press:
        return False
    if published_after:
        date_key = int(published_after.replace("-", ""))
        if metadata.get("published_date_key", 0) < date_key:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="금융 뉴스 질의 세트 평가")
    parser.add_argument("--queries", type=Path, default=Path("data/news/evaluation_queries.json"))
    parser.add_argument("--chroma-path", type=Path, default=Path("data/chroma"))
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--output", type=Path, default=Path("data/news/query_evaluation.json"))
    args = parser.parse_args()

    with args.queries.open("r", encoding="utf-8") as file:
        queries = json.load(file)
    if not isinstance(queries, list) or not queries:
        raise ValueError("queries 파일은 비어 있지 않은 리스트여야 합니다.")

    payload = evaluate_queries(
        queries,
        chroma_path=args.chroma_path,
        collection=args.collection,
        model_name=args.model,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)

    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"[완료] 질의 평가 {payload['summary']['query_count']}건 -> {args.output}")


if __name__ == "__main__":
    main()
