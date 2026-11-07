"""금융 뉴스 벡터 인덱싱 Airflow DAG.

news pipeline -> chunk -> embed -> validate -> ChromaDB -> search

Airflow UI에서 수동 Trigger 하도록 ``schedule=None``으로 둔다.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.models.param import Param
from airflow.operators.bash import BashOperator


PROJECT_ROOT = Path(os.environ.get("FINANCIAL_AGENT_ROOT", Path(__file__).resolve().parents[1]))
PYTHON = os.environ.get("DE_PYTHON", "python3")

default_args = {
    "owner": "financial-ai-agent",
    "retries": 1,
    "retry_delay": timedelta(minutes=3),
}

with DAG(
    dag_id="financial_news_vector_pipeline",
    description="뉴스 수집부터 ChromaDB 검색까지 실행하는 금융 RAG 준비 파이프라인",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2026, 7, 1),
    catchup=False,
    params={
        "query": Param("반도체 관련 최신 뉴스 요약", type="string", title="검색 질의"),
        "top_k": Param(5, type="integer", minimum=1, title="검색 결과 수"),
        "reset_collection": Param(False, type="boolean", title="컬렉션 초기화"),
        "upload_to_cloud": Param(False, type="boolean", title="GCS·BigQuery 적재"),
    },
    tags=["financial", "news", "rag", "vector"],
) as dag:
    collect_news = BashOperator(
        task_id="collect_news",
        bash_command=(
            f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_pipeline "
            "{% if not params.upload_to_cloud %} --local-only {% endif %}"
        ),
    )
    chunk_news = BashOperator(
        task_id="chunk_news",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_index_pipeline --stage chunk",
    )
    embed_news = BashOperator(
        task_id="embed_news",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_index_pipeline --stage embed",
    )
    validate_embeddings = BashOperator(
        task_id="validate_embeddings",
        bash_command=f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_index_pipeline --stage validate",
    )
    load_chromadb = BashOperator(
        task_id="load_chromadb",
        bash_command=(
            f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_index_pipeline --stage index "
            "{% if params.reset_collection %} --reset {% endif %}"
        ),
    )
    search_news = BashOperator(
        task_id="search_news",
        bash_command=(
            f"cd {PROJECT_ROOT} && {PYTHON} -m pipelines.news_index_pipeline --stage search "
            "--query '{{ params.query }}' --top-k {{ params.top_k }}"
        ),
    )

    collect_news >> chunk_news >> embed_news >> validate_embeddings >> load_chromadb >> search_news
