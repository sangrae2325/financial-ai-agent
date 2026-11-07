"""ChromaDB에 금융 뉴스 임베딩을 적재하고 검색한다."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from embedding.news_embedding import DEFAULT_EMBEDDING_MODEL


DEFAULT_COLLECTION = "financial_news"


def load_embedding_payload(path: str | Path) -> dict[str, Any]:
    """임베딩 JSON을 읽고 최소 스키마를 검증한다."""
    with Path(path).open("r", encoding="utf-8") as file:
        payload = json.load(file)

    records = payload.get("records") if isinstance(payload, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError("임베딩 JSON의 records가 비어 있거나 리스트가 아닙니다.")
    return payload


def upsert_news_embeddings(
    payload: dict[str, Any],
    *,
    chroma_path: str | Path,
    collection_name: str = DEFAULT_COLLECTION,
    reset: bool = False,
) -> int:
    """청크 ID를 기준으로 뉴스 벡터를 ChromaDB에 upsert한다."""
    chromadb = _load_chromadb()
    records = payload["records"]
    client = chromadb.PersistentClient(path=str(chroma_path))

    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(
        ids=[record["chunk_id"] for record in records],
        documents=[record["text"] for record in records],
        embeddings=[record["embedding"] for record in records],
        metadatas=[_flatten_metadata(record) for record in records],
    )
    return collection.count()


def search_news(
    query: str,
    *,
    chroma_path: str | Path,
    collection_name: str = DEFAULT_COLLECTION,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    top_k: int = 5,
    keywords: list[str] | None = None,
    press: str | None = None,
    published_after: str | None = None,
) -> dict[str, Any]:
    """의미 검색 후보를 키워드·최신성까지 반영해 재정렬한다.

    ChromaDB는 넉넉한 후보군을 의미 유사도로 가져오고, 이 함수는 질문에서 추출한
    정확 키워드와 기사 발행일을 더해 최종 순서를 결정한다. metadata 필터는 Chroma
    조회 시점에 먼저 적용되므로 재정렬 때문에 필터 조건이 깨지지 않는다.
    """
    if not query.strip():
        raise ValueError("검색 질의가 비어 있습니다.")
    if top_k <= 0:
        raise ValueError("top_k는 1 이상이어야 합니다.")

    chromadb = _load_chromadb()
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise RuntimeError("ChromaDB 컬렉션이 없습니다. 먼저 index 단계를 실행하세요.") from exc

    if collection.count() == 0:
        raise RuntimeError("ChromaDB 컬렉션이 비어 있습니다. 먼저 index 단계를 실행하세요.")

    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    vector = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]
    where = build_where_filter(press=press, published_after=published_after)
    normalized_keywords = _normalize_keywords(keywords or [])
    candidate_count = min(max(top_k * 4, top_k), collection.count())
    result = collection.query(
        query_embeddings=[vector.tolist()],
        n_results=candidate_count,
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    candidates_by_id = {
        hit["chunk_id"]: hit for hit in _result_to_hits(result)
    }

    # 의미 검색 상위권에 정확한 고유명사가 없을 수 있다. 키워드를 실제로 포함한
    # 문서도 별도 후보로 합쳐서, "삼성전자"처럼 정확도가 중요한 질문을 보강한다.
    for keyword in normalized_keywords:
        keyword_result = collection.query(
            query_embeddings=[vector.tolist()],
            n_results=candidate_count,
            where=where,
            where_document={"$contains": keyword},
            include=["documents", "metadatas", "distances"],
        )
        for hit in _result_to_hits(keyword_result):
            previous = candidates_by_id.get(hit["chunk_id"])
            if previous is None or hit["distance"] < previous["distance"]:
                candidates_by_id[hit["chunk_id"]] = hit

    candidates = list(candidates_by_id.values())
    hits = select_diverse_hits(
        rerank_news_hits(candidates, keywords=normalized_keywords), top_k=top_k
    )
    return {
        "query": query,
        "where": where,
        "top_k": top_k,
        "candidate_count": len(candidates),
        "keywords": normalized_keywords,
        "retrieval_method": "semantic + keyword + recency",
        "hit_count": len(hits),
        "hits": hits,
    }


def _result_to_hits(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Chroma query 응답의 첫 query 결과를 프로젝트 공통 hit 형태로 바꾼다."""
    ids = result["ids"][0]
    documents = result["documents"][0]
    metadatas = result["metadatas"][0]
    distances = result["distances"][0]
    return [
        {
            "chunk_id": chunk_id,
            "text": document,
            "metadata": metadata,
            "distance": float(distance),
        }
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances, strict=True
        )
    ]


def rerank_news_hits(
    candidates: list[dict[str, Any]], *, keywords: list[str]
) -> list[dict[str, Any]]:
    """후보 청크를 의미 유사도·키워드 일치·최신성으로 안정적으로 재정렬한다."""
    normalized_keywords = _normalize_keywords(keywords)
    candidate_dates = [
        published_date
        for hit in candidates
        if (published_date := _metadata_date(hit.get("metadata", {}))) is not None
    ]
    latest_date = max(candidate_dates, default=None)
    ranked_hits: list[dict[str, Any]] = []
    for hit in candidates:
        metadata = hit.get("metadata", {})
        semantic_score = max(0.0, min(1.0, 1 - float(hit.get("distance", 1.0))))
        keyword_score = _keyword_match_score(hit, normalized_keywords)
        recency_score = _recency_score(_metadata_date(metadata), latest_date)

        # 키워드가 없다면 의미 검색의 비중을 높여, 빈 키워드 때문에 품질이 낮아지는
        # 일을 피한다. Gemini 검색 계획의 키워드는 정확명사 보강 용도로만 쓴다.
        if normalized_keywords:
            hybrid_score = semantic_score * 0.65 + keyword_score * 0.25 + recency_score * 0.10
        else:
            hybrid_score = semantic_score * 0.85 + recency_score * 0.15

        ranked_hits.append(
            {
                **hit,
                "score_components": {
                    "semantic": round(semantic_score, 4),
                    "keyword": round(keyword_score, 4),
                    "recency": round(recency_score, 4),
                },
                "hybrid_score": round(hybrid_score, 4),
            }
        )
    return sorted(
        ranked_hits,
        key=lambda hit: (hit["hybrid_score"], hit["score_components"]["semantic"]),
        reverse=True,
    )


def select_diverse_hits(ranked_hits: list[dict[str, Any]], *, top_k: int) -> list[dict[str, Any]]:
    """같은 기사 청크가 반복되지 않도록 서로 다른 원문을 우선 선택한다."""
    selected: list[dict[str, Any]] = []
    seen_documents: set[str] = set()
    for hit in ranked_hits:
        metadata = hit.get("metadata", {})
        document_id = str(
            metadata.get("document_id")
            or metadata.get("url")
            or str(hit.get("chunk_id", "")).rsplit("_chunk_", maxsplit=1)[0]
        )
        if document_id in seen_documents:
            continue
        seen_documents.add(document_id)
        selected.append(hit)
        if len(selected) == top_k:
            break
    return selected


def get_indexed_chunk_ids(
    *, chroma_path: str | Path, collection_name: str = DEFAULT_COLLECTION
) -> set[str]:
    """현재 ChromaDB에 있는 청크 ID를 반환한다.

    증분 인덱싱은 이 집합에 없는 청크만 임베딩하므로, 기존 뉴스의 임베딩 비용을
    매일 다시 내지 않는다. 컬렉션이 없는 첫 실행은 빈 집합으로 처리한다.
    """
    chromadb = _load_chromadb()
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        return set()
    result = collection.get(include=[])
    return set(result["ids"])


def build_where_filter(
    *, press: str | None = None, published_after: str | None = None
) -> dict[str, Any] | None:
    """Chroma where 조건을 만든다. 둘 다 주면 $and 조건을 사용한다."""
    clauses: list[dict[str, Any]] = []
    if press:
        clauses.append({"press": press})
    if published_after:
        clauses.append({"published_date_key": {"$gte": _date_to_key(published_after)}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _flatten_metadata(record: dict[str, Any]) -> dict[str, str | int | float | bool]:
    """ChromaDB가 지원하는 평탄한 metadata만 남긴다."""
    metadata = dict(record.get("metadata", {}))
    metadata.update(
        {
            "document_id": str(record["document_id"]),
            "chunk_index": int(record["chunk_index"]),
        }
    )
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(value, (str, int, float, bool)) and value != ""
    }


def _date_to_key(value: str) -> int:
    """YYYY-MM-DD 날짜 필터를 Chroma 비교용 YYYYMMDD 정수로 바꾼다."""
    parts = value.split("-")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError("published_after는 YYYY-MM-DD 형식이어야 합니다.")
    year, month, day = (int(part) for part in parts)
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise ValueError("published_after 날짜가 올바르지 않습니다.")
    return year * 10000 + month * 100 + day


def _normalize_keywords(keywords: list[str]) -> list[str]:
    """정확 일치 점수에 쓸 의미 있는 키워드만 중복 없이 정리한다."""
    normalized: list[str] = []
    for keyword in keywords:
        text = re.sub(r"\s+", " ", str(keyword)).strip().lower()
        if len(text) < 2 or text in normalized:
            continue
        normalized.append(text)
    return normalized


def _keyword_match_score(hit: dict[str, Any], keywords: list[str]) -> float:
    """제목은 본문보다 중요한 정확 키워드 신호로 간주한다."""
    if not keywords:
        return 0.0
    metadata = hit.get("metadata", {})
    title = str(metadata.get("title", "")).lower()
    text = str(hit.get("text", "")).lower()
    matched = 0.0
    for keyword in keywords:
        if keyword in title:
            matched += 1.0
        elif keyword in text:
            matched += 0.7
    return min(1.0, matched / len(keywords))


def _metadata_date(metadata: dict[str, Any]) -> date | None:
    """청크 metadata의 정규화 날짜를 date 객체로 바꾼다."""
    value = metadata.get("published_date") or metadata.get("published_at")
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(value or ""))
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


def _recency_score(published_date: date | None, latest_date: date | None) -> float:
    """후보군의 가장 최신 기사와 비교해 30일 안에서 최신성 점수를 계산한다."""
    if published_date is None or latest_date is None:
        return 0.0
    days_old = max(0, (latest_date - published_date).days)
    return max(0.0, 1 - days_old / 30)


def _load_chromadb() -> Any:
    try:
        import chromadb
    except ImportError as exc:
        raise ImportError("chromadb가 필요합니다. requirements.txt를 설치하세요.") from exc
    return chromadb
