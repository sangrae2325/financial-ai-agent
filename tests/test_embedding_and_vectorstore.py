"""임베딩 payload와 Chroma 검색 조건 생성 단위 테스트."""

import unittest

from embedding.news_embedding import embed_news_chunks
from vectorstore.chroma import build_where_filter, rerank_news_hits, select_diverse_hits


CHUNK = {
    "chunk_id": "news_abc_chunk_0",
    "document_id": "abc",
    "chunk_index": 0,
    "text": "제목: 반도체 뉴스\n본문: 테스트 본문",
    "metadata": {
        "title": "반도체 뉴스",
        "press": "테스트경제",
        "published_at": "2026-07-19 10:00",
        "url": "https://example.com/news",
    },
}


class FakeModel:
    """SentenceTransformer 없이 임베딩 payload 형태를 검증하는 테스트 모델."""

    def encode(self, texts, **kwargs):
        class Vector(list):
            def tolist(self):
                return list(self)

        return [Vector([0.1, 0.2]) for _ in texts]


class EmbeddingAndVectorstoreTest(unittest.TestCase):
    def test_embed_news_chunks_builds_chroma_ready_records(self) -> None:
        payload = embed_news_chunks([CHUNK], model=FakeModel())

        self.assertEqual(payload["record_count"], 1)
        self.assertEqual(payload["embedding_dim"], 2)
        self.assertEqual(payload["records"][0]["chunk_id"], "news_abc_chunk_0")

    def test_build_where_filter_combines_news_conditions(self) -> None:
        where = build_where_filter(press="테스트경제", published_after="2026-07-19")

        self.assertEqual(
            where,
            {
                "$and": [
                    {"press": "테스트경제"},
                    {"published_date_key": {"$gte": 20260719}},
                ]
            },
        )

    def test_hybrid_rerank_promotes_exact_keyword_and_recent_article(self) -> None:
        """의미 점수가 조금 낮아도 정확 키워드와 최신성이 있으면 순위가 올라간다."""
        candidates = [
            {
                "chunk_id": "old-semantic",
                "text": "관련 시장 분석 본문",
                "distance": 0.10,
                "metadata": {"title": "시장 분석", "published_date": "2026-06-01"},
            },
            {
                "chunk_id": "recent-keyword",
                "text": "삼성전자 실적과 반도체 업황 본문",
                "distance": 0.18,
                "metadata": {"title": "삼성전자 반도체", "published_date": "2026-07-01"},
            },
        ]

        ranked = rerank_news_hits(candidates, keywords=["삼성전자", "반도체"])

        self.assertEqual(ranked[0]["chunk_id"], "recent-keyword")
        self.assertGreater(ranked[0]["hybrid_score"], ranked[1]["hybrid_score"])

    def test_select_diverse_hits_keeps_one_chunk_per_article(self) -> None:
        """상위 청크가 같은 원문에서 나와도 답변 근거는 여러 기사로 구성한다."""
        ranked_hits = [
            {"chunk_id": "article-a_chunk_0", "metadata": {"document_id": "article-a"}},
            {"chunk_id": "article-a_chunk_1", "metadata": {"document_id": "article-a"}},
            {"chunk_id": "article-b_chunk_0", "metadata": {"document_id": "article-b"}},
        ]

        selected = select_diverse_hits(ranked_hits, top_k=2)

        self.assertEqual([hit["chunk_id"] for hit in selected], ["article-a_chunk_0", "article-b_chunk_0"])
