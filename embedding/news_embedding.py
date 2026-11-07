"""금융 뉴스 청크를 로컬 임베딩 JSON으로 변환한다."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


DEFAULT_EMBEDDING_MODEL = "kekeappa/kor-static-embedding-128"


def embed_news_chunks(
    chunks: list[dict[str, Any]],
    *,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = 16,
    model: Any | None = None,
) -> dict[str, Any]:
    """뉴스 청크를 임베딩하고 ChromaDB 적재용 payload를 만든다.

    ``model`` 인자는 단위 테스트에서 가짜 모델을 주입할 수 있도록 열어 둔다.
    실사용 시에는 SentenceTransformer를 지연 로드해 Collector 계층에 무거운
    ML 의존성이 전파되지 않도록 한다.
    """
    if not chunks:
        raise ValueError("임베딩할 뉴스 청크가 없습니다.")
    if batch_size <= 0:
        raise ValueError("batch_size는 1 이상이어야 합니다.")

    _validate_chunks(chunks)
    if model is None:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)

    vectors = model.encode(
        [chunk["text"] for chunk in chunks],
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    records: list[dict[str, Any]] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        records.append(
            {
                "chunk_id": chunk["chunk_id"],
                "document_id": chunk["document_id"],
                "chunk_index": chunk["chunk_index"],
                "text": chunk["text"],
                "embedding": [float(value) for value in vector.tolist()],
                "metadata": chunk["metadata"],
            }
        )

    return {
        "embedding_model": model_name,
        "embedding_dim": len(records[0]["embedding"]),
        "embedded_at": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "records": records,
    }


def _validate_chunks(chunks: list[dict[str, Any]]) -> None:
    """임베딩에 필요한 최소 청크 스키마를 검증한다."""
    required_fields = ("chunk_id", "document_id", "chunk_index", "text", "metadata")
    for index, chunk in enumerate(chunks):
        if not isinstance(chunk, dict):
            raise ValueError(f"{index}번 청크가 딕셔너리 형식이 아닙니다.")
        for field in required_fields:
            if field not in chunk:
                raise ValueError(f"{index}번 청크에 {field} 필드가 없습니다.")
        if not isinstance(chunk["text"], str) or not chunk["text"].strip():
            raise ValueError(f"{index}번 청크의 text가 비어 있습니다.")
