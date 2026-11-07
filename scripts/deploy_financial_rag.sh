#!/usr/bin/env bash
# 현재 로컬 ChromaDB 인덱스를 포함한 금융 뉴스 RAG UI를 Cloud Run에 배포한다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${RAG_SERVICE_NAME:-financial-news-rag}"
SECRET_NAME="${GEMINI_SECRET_NAME:-financial-gemini-api-key}"
RUNTIME_SERVICE_ACCOUNT_NAME="${RUNTIME_SERVICE_ACCOUNT_NAME:-financial-rag-runtime}"
RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-${RUNTIME_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-3.5-flash-lite}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[오류] GCP_PROJECT_ID를 설정하세요."
  exit 1
fi

if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[오류] Secret Manager에 ${SECRET_NAME}이 없습니다. 먼저 scripts/setup_gemini_secret.sh를 실행하세요."
  exit 1
fi

if ! gcloud iam service-accounts describe "${RUNTIME_SERVICE_ACCOUNT}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[오류] 런타임 서비스 계정이 없습니다: ${RUNTIME_SERVICE_ACCOUNT}"
  echo "먼저 scripts/setup_gemini_secret.sh를 실행하세요."
  exit 1
fi

# 별도로 설정하지 않으면 같은 프로젝트의 금융 로그 수집기 URL을 자동으로 찾는다.
LOG_COLLECTOR_URL="${LOG_COLLECTOR_URL:-}"
if [[ -z "${LOG_COLLECTOR_URL}" ]]; then
  LOG_COLLECTOR_URL="$(gcloud run services describe financial-agent-event-collector \
    --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)' 2>/dev/null || true)"
fi

ENV_VARS="GEMINI_MODEL=${GEMINI_MODEL}"
if [[ -n "${LOG_COLLECTOR_URL}" ]]; then
  ENV_VARS+=",LOG_COLLECTOR_URL=${LOG_COLLECTOR_URL}"
fi

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --source="${PROJECT_ROOT}" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --service-account="${RUNTIME_SERVICE_ACCOUNT}" \
  --set-env-vars="${ENV_VARS}" \
  --set-secrets="GEMINI_API_KEY=${SECRET_NAME}:latest" \
  --cpu=1 \
  --memory=2Gi \
  --concurrency=5 \
  --min-instances=0 \
  --max-instances=1 \
  --timeout=300 \
  --port=8080

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo "[완료] 금융 뉴스 RAG: ${SERVICE_URL}"
echo "[확인] ${SERVICE_URL} 접속 후 질문을 입력해 보세요."
