#!/usr/bin/env bash
# Gemini API 키를 Secret Manager에 저장하고 금융 RAG 런타임에만 읽기 권한을 준다.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
SECRET_NAME="${GEMINI_SECRET_NAME:-financial-gemini-api-key}"
GEMINI_API_KEY_VALUE="${GEMINI_API_KEY:-}"
RUNTIME_SERVICE_ACCOUNT_NAME="${RUNTIME_SERVICE_ACCOUNT_NAME:-financial-rag-runtime}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[오류] GCP_PROJECT_ID를 설정하세요."
  exit 1
fi
if [[ -z "${GEMINI_API_KEY_VALUE}" ]]; then
  echo "[오류] GEMINI_API_KEY를 현재 셸에 설정하세요. 키는 Secret Manager에만 저장됩니다."
  exit 1
fi

if ! gcloud secrets describe "${SECRET_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud secrets create "${SECRET_NAME}" \
    --project="${PROJECT_ID}" \
    --replication-policy=automatic
fi

# 표준 출력에 키를 노출하지 않고 새 Secret 버전을 추가한다.
printf '%s' "${GEMINI_API_KEY_VALUE}" | \
  gcloud secrets versions add "${SECRET_NAME}" --project="${PROJECT_ID}" --data-file=- >/dev/null

RUNTIME_SERVICE_ACCOUNT="${RUNTIME_SERVICE_ACCOUNT:-${RUNTIME_SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com}"
if ! gcloud iam service-accounts describe "${RUNTIME_SERVICE_ACCOUNT}" \
  --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${RUNTIME_SERVICE_ACCOUNT_NAME}" \
    --project="${PROJECT_ID}" \
    --display-name="Financial AI Agent Cloud Run runtime"
fi

gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${RUNTIME_SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor" >/dev/null

echo "[완료] Secret Manager: ${SECRET_NAME}"
echo "[권한] ${RUNTIME_SERVICE_ACCOUNT} → secretAccessor"
