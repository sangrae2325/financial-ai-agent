# Financial AI Agent

금융 뉴스와 시장 데이터를 수집해 RAG 기반 금융 질의응답 Agent로 확장하는 프로젝트다.

## 현재 뉴스 인덱싱 흐름

```text
News Collector → Validation → Local/GCS/BigQuery
                                  ↓
                         Normalize → Chunk
                                  ↓
                     SentenceTransformer Embedding
                                  ↓
                     ChromaDB → Vector Search → RAG Context
```

## 로컬 벡터 인덱스 실행

```bash
source .venv/bin/activate
pip install -r requirements.txt

# data/news/news.json을 청킹·임베딩·검증·ChromaDB 적재·검색까지 실행
python -m pipelines.news_index_pipeline --stage all --reset \
  --query "반도체 관련 최신 뉴스 요약" \
  --top-k 3
```

생성 파일은 `data/news/chunks.json`, `data/news/embeddings.json`,
`data/news/search_results.json`, `data/chroma/`에 저장된다.

## Week 4: Gemini 기반 금융 뉴스 RAG

Week 3에서 만든 `financial_news` ChromaDB를 그대로 사용한다. Week 4의
페르소나 검색 예제와 달리, 이 프로젝트에서는 질문을 **금융 뉴스 검색어**와
선택적인 **언론사·날짜 metadata filter**로 해석한다.

```text
금융 질문 → Gemini 검색 계획 → ChromaDB 의미 검색 + metadata filter
         → 뉴스 청크 근거(context) → Gemini 근거 기반 답변
```

먼저 금융 프로젝트 루트에 `.env`를 만들고 API 키를 넣는다. `.env`는 Git에
포함되지 않으므로 키를 코드나 제출 파일에 적지 않는다.

```bash
cd /Users/sangrae/DE/financial-ai-agent
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# .env 파일의 GEMINI_API_KEY=... 부분에 본인 키 입력
# GEMINI_MODEL은 gemini-3.5-flash-lite로 유지
```

터미널 RAG 실행 예시다. 결과 전체는 `data/news/rag_answer.json`에 저장되고,
터미널에는 답변만 간단히 출력된다.

```bash
python -m scripts.financial_rag_demo \
  --query "SK하이닉스 ADR 공모가 기업가치에 어떤 의미가 있어?" \
  --top-k 3
```

명시적인 업무 조건이 있을 때는 벡터 검색 전에 metadata filter를 적용할 수 있다.

```bash
python -m scripts.financial_rag_demo \
  --query "반도체 투자 관련 뉴스 요약해줘" \
  --press "서울경제" \
  --published-after "2026-07-10" \
  --top-k 3
```

## 하이브리드 뉴스 검색

RAG 검색은 단순 벡터 유사도 순서가 아니라 세 신호를 함께 사용한다.

```text
의미 유사도 65% + 정확 키워드 일치 25% + 최신성 10%
```

Gemini 검색 계획이 추출한 종목명·산업명 같은 키워드를 실제로 포함한 기사도 후보에
합친다. 따라서 의미는 비슷하지만 질문의 핵심 고유명사가 없는 기사보다, 정확한
키워드가 있고 최신인 기사가 상단에 오기 쉽다. 같은 원문의 여러 청크는 최종 결과에서
하나만 남겨 여러 기사 근거를 제공한다. 언론사·날짜 metadata filter는 후보 검색 전에
먼저 적용되므로 재정렬 후에도 조건을 위반하지 않는다.

Gemini 없이 검색 순위만 점검하려면 아래처럼 정확 키워드를 직접 줄 수 있다.

```bash
python -m pipelines.news_index_pipeline --stage search \
  --query "삼성전자 반도체 관련 최신 이슈" \
  --keywords "삼성전자,반도체" \
  --top-k 3
```

출력의 `hybrid`는 최종 점수이고, 괄호 안에는 의미·키워드·최신성 점수가 각각 표시된다.

화면으로 확인하려면 아래 명령을 실행한다. 브라우저에서 표시되는 답변의
`[근거 N]` 번호를 펼쳐 보면 실제로 검색된 청크·언론사·날짜·원문 URL을 확인할 수 있다.

```bash
streamlit run app.py
```

### Streamlit 익명 행동 로그 연동

Week 5의 `log-collector`를 실행한 상태에서 `LOG_COLLECTOR_URL`을 설정하면 금융
UI가 `page_view`, `data_loaded`, `record_search`, `client_error` 이벤트를 전송한다.
질문 원문·뉴스 본문·API 오류 메시지는 보내지 않고, 기사 수·검색어 길이·검색 결과 수
같은 최소 통계만 전송한다. 로그 수집기가 꺼져 있어도 RAG 검색은 계속 동작한다.

```bash
# 터미널 A: Week 5 로그 수집기
cd /Users/sangrae/DE/week5/log-collector
source .venv/bin/activate
uv pip install -r requirements-dev.txt
uvicorn main:app --reload --port 8080

# 터미널 B: 금융 AI Agent UI
cd /Users/sangrae/DE/financial-ai-agent
source .venv/bin/activate
export LOG_COLLECTOR_URL=http://localhost:8080
streamlit run app.py
```

금융 UI에서 질문을 실행한 뒤 터미널 A에 `event_type: "record_search"` 로그가
표시되면 연동 성공이다.

## Cloud Run 배포 준비: Gemini Secret

Cloud Run에는 Gemini 키를 평문 환경변수나 이미지 파일로 넣지 않는다. 아래 스크립트는
키를 Secret Manager에 등록하고, 금융 RAG 런타임 서비스 계정에만
`secretAccessor` 권한을 부여한다. `read -s`는 입력 중인 키를 터미널에 보이지 않게 한다.

```bash
export GCP_PROJECT_ID=lively-nimbus-501500-d8
read -s GEMINI_API_KEY
export GEMINI_API_KEY
bash scripts/setup_gemini_secret.sh
unset GEMINI_API_KEY
```

## 매일 뉴스 누적 수집과 증분 인덱싱

뉴스 수집은 네이버 금융 메인 뉴스의 최근 **3페이지**를 기본으로 가져온다. 매일의
원본을 `data/news/raw/YYYY-MM-DD/news.json`에 보관하고, URL 기준으로 중복을 제거한
누적 목록을 `data/news/news.json`에 유지한다.
그 다음 `incremental` 단계는 이미 ChromaDB에 있는 청크 ID를 확인해 **새 청크만**
임베딩하고 upsert한다.

```bash
# 1) 오늘 수집한 원본 보관 + 기존 뉴스 목록에 누적
python -m pipelines.news_pipeline --local-only

# 2) 새 청크만 임베딩하고 ChromaDB에 추가
python -m pipelines.news_index_pipeline --stage incremental
```

수집 범위는 필요에 따라 조절할 수 있다. 페이지가 늘수록 기사 본문 요청 수도 늘어나므로,
일상 수집은 3페이지 정도로 시작하고 최초 데이터 확충 때만 더 크게 실행하는 편이 좋다.

```bash
# 최근 5페이지를 한 번에 수집
python -m pipelines.news_pipeline --local-only --pages 5
```

자동 실행은 Airflow Scheduler가 켜져 있을 때만 가능하다. 실습 DAG의 수동 Trigger로
위 과정을 먼저 확인한 뒤, 운영 단계에서는 평일 저녁과 같이 시장 마감 뒤 시간으로
cron schedule을 설정하는 것이 적절하다.

## 시장 시세 수집 (Phase 2)

뉴스의 원인 분석을 실제 가격 움직임과 연결하기 위해 국내 주요 종목의
최신 시세를 별도로 수집한다. Collector는 가격만 가져오고,
Pipeline은 날짜별 원본과 누적 JSON 저장을 담당한다.

```bash
python -m pipelines.stock_pipeline
```

결과는 `data/stocks/raw/YYYY-MM-DD/stocks.json`과 `data/stocks/stocks.json`에
저장된다.

수집 대상은 `data/config/stock_universe.json`에 있는 25개 국내 주요 종목이다.
새 종목을 넣을 때는 Collector 코드를 수정하지 않고 아래처럼 종목 코드와 이름만
추가하면 된다.

```json
"035420": "NAVER"
```

종목명이 질문에 직접 포함되면 RAG는 `data/stocks/stocks.json`의 최신 시세를
자동으로 읽어 뉴스 근거와 함께 Gemini에 전달한다. 답변에서는 뉴스는 `[근거 N]`,
시세는 `[시장 데이터]`로 구분해 인용한다.

## 환율 수집과 RAG 연결 (Phase 3)

환율은 USD 기준 API의 `KRW` 값을 사용한다. 즉 `rates["KRW"]`는 **1 USD당
KRW**다. GCP 설정이 아직 없어도 아래처럼 로컬 JSON만 갱신할 수 있다.

```bash
python -m pipelines.exchange_pipeline --local-only
```

`환율`, `원달러`, `원/달러`, `USD/KRW`, `외환`이 포함된 질문이면 RAG는
`data/exchange/exchange.json`의 저장된 환율을 읽어 뉴스 근거와 함께 전달한다.
답변과 화면에서는 이 값을 `[시장 데이터]`로 구분하고, 기준 시각도 함께 표시한다.

```bash
python -m scripts.financial_rag_demo \
  --query "원달러 환율 수준과 관련 뉴스 이슈를 알려줘" \
  --top-k 5
```

## 메타데이터 필터 검색

```bash
python -m pipelines.news_index_pipeline --stage search \
  --query "반도체 투자 관련 뉴스" \
  --press "한국경제" \
  --published-after "2026-07-10" \
  --top-k 3
```

## Airflow 실습 실행

Airflow는 무거운 선택 의존성으로 분리했다. Python 3.12 환경에서 constraints와 함께 설치한다.

```bash
export AIRFLOW_VERSION=2.10.5
export CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-3.12.txt"
pip install -r requirements-airflow.txt --constraint "$CONSTRAINT_URL"
```

`dags/financial_news_vector_pipeline_dag.py`를 `$AIRFLOW_HOME/dags/`에 연결하면,
수동 Trigger로 `collect_news → chunk_news → embed_news → validate_embeddings → load_chromadb → search_news`를 실행할 수 있다.
기본값은 로컬 수집·인덱싱 모드이며, GCS와 BigQuery 설정이 준비된 경우에만
Trigger 화면에서 `GCS·BigQuery 적재`를 켠다.
