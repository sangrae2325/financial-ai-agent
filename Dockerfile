# 금융 뉴스 RAG Streamlit 앱의 Cloud Run 이미지
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 실행에 필요한 코드와, 현재 구축한 읽기 전용 검색 인덱스만 이미지에 담는다.
COPY app ./app
COPY rag ./rag
COPY vectorstore ./vectorstore
COPY embedding ./embedding
COPY preprocessing ./preprocessing
COPY app.py .
COPY data/chroma ./data/chroma
COPY data/news/news.json ./data/news/news.json
COPY data/stocks/stocks.json ./data/stocks/stocks.json
COPY data/exchange/exchange.json ./data/exchange/exchange.json

# 첫 사용자 요청에서 모델을 받느라 기다리지 않도록, 이미지 빌드 시 임베딩 모델을 받는다.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('kekeappa/kor-static-embedding-128')"

EXPOSE 8080

CMD ["sh", "-c", "streamlit run app.py --server.address=0.0.0.0 --server.port=${PORT:-8080} --server.headless=true --server.fileWatcherType=none"]
