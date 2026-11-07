"""저장된 금융 뉴스에서 청크·임베딩·ChromaDB 인덱스를 생성한다.

각 단계는 개별 실행할 수 있고, ``--stage all``로 전체 인덱싱을 실행할 수 있다.
Collector/Storage 계층은 건드리지 않으며 이미 저장된 ``data/news/news.json``을
입력으로 사용한다.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from embedding.news_embedding import DEFAULT_EMBEDDING_MODEL, embed_news_chunks
from preprocessing.chunk import chunk_news
from preprocessing.preprocess import normalize_news
from rag.financial_rag import build_news_context
from vectorstore.chroma import (
    DEFAULT_COLLECTION,
    get_indexed_chunk_ids,
    load_embedding_payload,
    search_news,
    upsert_news_embeddings,
)


DEFAULT_NEWS_PATH = Path("data/news/news.json")
DEFAULT_CHUNKS_PATH = Path("data/news/chunks.json")
DEFAULT_EMBEDDINGS_PATH = Path("data/news/embeddings.json")
DEFAULT_CHROMA_PATH = Path("data/chroma")
DEFAULT_SEARCH_PATH = Path("data/news/search_results.json")


def create_chunks(input_path: Path, output_path: Path) -> dict[str, Any]:
    """원본 뉴스 JSON을 정규화하고 임베딩용 청크 JSON으로 저장한다."""
    articles = _load_list(input_path, "뉴스")
    chunks = chunk_news(normalize_news(articles))
    payload = {"source": str(input_path), "chunk_count": len(chunks), "chunks": chunks}
    _save_json(payload, output_path)
    return payload


def create_embeddings(
    chunks_path: Path,
    output_path: Path,
    *,
    model_name: str,
    batch_size: int,
) -> dict[str, Any]:
    """청크 JSON을 임베딩 JSON으로 저장한다."""
    payload = _load_object(chunks_path, "청크")
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        raise ValueError("청크 JSON의 chunks 필드가 리스트가 아닙니다.")
    embeddings = embed_news_chunks(chunks, model_name=model_name, batch_size=batch_size)
    embeddings["source_chunks"] = str(chunks_path)
    _save_json(embeddings, output_path)
    return embeddings


def validate_embeddings(path: Path) -> dict[str, Any]:
    """적재 전 임베딩 개수·차원·텍스트·ID를 검증한다."""
    payload = load_embedding_payload(path)
    records = payload["records"]
    dimension = payload.get("embedding_dim")
    seen_ids: set[str] = set()
    for index, record in enumerate(records):
        chunk_id = record.get("chunk_id")
        vector = record.get("embedding")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError(f"{index}번 레코드의 chunk_id가 비어 있습니다.")
        if chunk_id in seen_ids:
            raise ValueError(f"중복 chunk_id가 있습니다: {chunk_id}")
        if not isinstance(vector, list) or not vector:
            raise ValueError(f"{index}번 레코드의 embedding이 비어 있습니다.")
        if dimension is not None and len(vector) != dimension:
            raise ValueError(f"{index}번 레코드의 임베딩 차원이 다릅니다.")
        seen_ids.add(chunk_id)
    return {"record_count": len(records), "embedding_dim": dimension}


def index_embeddings(
    embeddings_path: Path,
    chroma_path: Path,
    *,
    collection: str,
    reset: bool,
) -> int:
    """검증된 임베딩 JSON을 ChromaDB에 적재한다."""
    payload = load_embedding_payload(embeddings_path)
    return upsert_news_embeddings(
        payload,
        chroma_path=chroma_path,
        collection_name=collection,
        reset=reset,
    )


def run_incremental_index(
    *,
    input_path: Path,
    chunks_path: Path,
    embeddings_path: Path,
    chroma_path: Path,
    collection: str,
    model_name: str,
    batch_size: int,
) -> dict[str, Any]:
    """전체 누적 뉴스 중 ChromaDB에 없는 청크만 새로 임베딩·적재한다."""
    chunk_payload = create_chunks(input_path, chunks_path)
    indexed_ids = get_indexed_chunk_ids(
        chroma_path=chroma_path, collection_name=collection
    )
    new_chunks = [
        chunk
        for chunk in chunk_payload["chunks"]
        if chunk["chunk_id"] not in indexed_ids
    ]
    if not new_chunks:
        return {
            "chunk_count": chunk_payload["chunk_count"],
            "new_chunk_count": 0,
            "indexed_count": len(indexed_ids),
        }

    embeddings = embed_news_chunks(
        new_chunks, model_name=model_name, batch_size=batch_size
    )
    embeddings["source_chunks"] = str(chunks_path)
    _save_json(embeddings, embeddings_path)
    validate_embeddings(embeddings_path)
    total_count = index_embeddings(
        embeddings_path, chroma_path, collection=collection, reset=False
    )
    return {
        "chunk_count": chunk_payload["chunk_count"],
        "new_chunk_count": len(new_chunks),
        "indexed_count": total_count,
    }


def run_search(
    *,
    query: str,
    chroma_path: Path,
    collection: str,
    model_name: str,
    top_k: int,
    press: str | None,
    published_after: str | None,
    keywords: list[str] | None,
    output_path: Path,
) -> dict[str, Any]:
    """검색 결과와 RAG 컨텍스트를 JSON으로 저장한다."""
    result = search_news(
        query,
        chroma_path=chroma_path,
        collection_name=collection,
        model_name=model_name,
        top_k=top_k,
        keywords=keywords,
        press=press,
        published_after=published_after,
    )
    result["context"] = build_news_context(result)
    _save_json(result, output_path)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="금융 뉴스 벡터 인덱스 파이프라인")
    parser.add_argument(
        "--stage",
        choices=("chunk", "embed", "validate", "index", "search", "all", "incremental"),
        required=True,
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_NEWS_PATH)
    parser.add_argument("--chunks-path", type=Path, default=DEFAULT_CHUNKS_PATH)
    parser.add_argument("--embeddings-path", type=Path, default=DEFAULT_EMBEDDINGS_PATH)
    parser.add_argument("--chroma-path", type=Path, default=DEFAULT_CHROMA_PATH)
    parser.add_argument("--collection", default=DEFAULT_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--query", default="반도체 관련 최신 뉴스 요약")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--press", default=None)
    parser.add_argument("--published-after", default=None)
    parser.add_argument(
        "--keywords",
        default="",
        help="선택: 쉼표로 구분한 정확 키워드 (예: 삼성전자,반도체)",
    )
    parser.add_argument("--search-output", type=Path, default=DEFAULT_SEARCH_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.stage == "incremental":
        result = run_incremental_index(
            input_path=args.input,
            chunks_path=args.chunks_path,
            embeddings_path=args.embeddings_path,
            chroma_path=args.chroma_path,
            collection=args.collection,
            model_name=args.model,
            batch_size=args.batch_size,
        )
        print(
            "[증분 적재 완료] "
            f"전체 청크={result['chunk_count']}건 | "
            f"신규 청크={result['new_chunk_count']}건 | "
            f"ChromaDB={result['indexed_count']}건"
        )
        return
    if args.stage in ("chunk", "all"):
        result = create_chunks(args.input, args.chunks_path)
        print(f"[완료] 청킹: {result['chunk_count']}건 -> {args.chunks_path}")
    if args.stage in ("embed", "all"):
        result = create_embeddings(args.chunks_path, args.embeddings_path, model_name=args.model, batch_size=args.batch_size)
        print(f"[완료] 임베딩: {result['record_count']}건 (dim={result['embedding_dim']}) -> {args.embeddings_path}")
    if args.stage in ("validate", "all"):
        result = validate_embeddings(args.embeddings_path)
        print(f"[품질 검증 통과] {result['record_count']}건, dim={result['embedding_dim']}")
    if args.stage in ("index", "all"):
        count = index_embeddings(args.embeddings_path, args.chroma_path, collection=args.collection, reset=args.reset)
        print(f"[완료] ChromaDB 적재: {count}건 -> {args.chroma_path}/{args.collection}")
    if args.stage in ("search", "all"):
        keywords = [keyword.strip() for keyword in args.keywords.split(",") if keyword.strip()]
        result = run_search(query=args.query, chroma_path=args.chroma_path, collection=args.collection, model_name=args.model, top_k=args.top_k, press=args.press, published_after=args.published_after, keywords=keywords, output_path=args.search_output)
        _print_search_summary(result, args.search_output)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{label} JSON 루트가 객체가 아닙니다.")
    return data


def _load_list(path: Path, label: str) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"{label} JSON 루트가 리스트가 아닙니다.")
    return data


def _save_json(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def _print_search_summary(result: dict[str, Any], output_path: Path) -> None:
    """제출 캡처에 필요한 검색 결과 핵심만 터미널에 출력한다."""
    print("\n[검색 결과]")
    print(f"질의: {result['query']}")
    print(f"필터(where): {json.dumps(result['where'], ensure_ascii=False)}")
    print(f"검색 방식: {result['retrieval_method']} | 키워드: {', '.join(result['keywords']) or '없음'}")
    print(f"결과 수: {result['hit_count']}건")
    for index, hit in enumerate(result["hits"], start=1):
        metadata = hit["metadata"]
        print(
            f"{index}. hybrid={hit['hybrid_score']:.4f} "
            f"(의미={hit['score_components']['semantic']:.2f}, "
            f"키워드={hit['score_components']['keyword']:.2f}, "
            f"최신성={hit['score_components']['recency']:.2f}) | "
            f"{metadata.get('press', '알 수 없음')} | "
            f"{metadata.get('published_date', '날짜 없음')}\n"
            f"   {metadata.get('title', '제목 없음')}"
        )
    print(f"[완료] 검색: {result['hit_count']}건 -> {output_path}")


if __name__ == "__main__":
    main()
