#!/usr/bin/env bash
# 금융 AI Agent 익명 로그 수집기를 Cloud Run에 배포한다.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${REGION:-asia-northeast3}"
SERVICE_NAME="${LOG_SERVICE_NAME:-financial-agent-event-collector}"
# Streamlit Cloud Run은 서버에서 collector를 호출하므로 CORS가 필요하지 않다.
# 이후 브라우저에서 직접 호출하는 UI를 붙일 때만 ALLOWED_ORIGIN을 설정한다.
ALLOWED_ORIGIN="${ALLOWED_ORIGIN:-}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[오류] GCP_PROJECT_ID를 설정하세요."
  exit 1
fi

ENV_VARS="GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
if [[ -n "${ALLOWED_ORIGIN}" ]]; then
  ENV_VARS+=",ALLOWED_ORIGIN=${ALLOWED_ORIGIN}"
fi

gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --source="${PROJECT_ROOT}/log_collector" \
  --region="${REGION}" \
  --allow-unauthenticated \
  --set-env-vars="${ENV_VARS}" \
  --cpu=1 \
  --memory=512Mi \
  --concurrency=40 \
  --min-instances=0 \
  --max-instances=1 \
  --timeout=60 \
  --port=8080

LOG_COLLECTOR_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" --region="${REGION}" --format='value(status.url)')"
echo "[완료] 금융 로그 수집기: ${LOG_COLLECTOR_URL}"
echo "export LOG_COLLECTOR_URL=${LOG_COLLECTOR_URL}"
