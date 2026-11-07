#!/usr/bin/env bash
# 선택: Cloud Logging의 금융 UI 이벤트를 BigQuery 데이터셋으로 라우팅한다.
set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
DATASET="${LOG_DATASET:-financial_agent_logs}"
SINK_NAME="${LOG_SINK_NAME:-financial-agent-events}"
REGION="${REGION:-asia-northeast3}"

if [[ -z "${PROJECT_ID}" ]]; then
  echo "[오류] GCP_PROJECT_ID를 설정하세요."
  exit 1
fi

gcloud services enable bigquery.googleapis.com --project="${PROJECT_ID}"
if ! bq show --dataset "${PROJECT_ID}:${DATASET}" >/dev/null 2>&1; then
  bq --location="${REGION}" mk --dataset "${PROJECT_ID}:${DATASET}"
fi
DESTINATION="bigquery.googleapis.com/projects/${PROJECT_ID}/datasets/${DATASET}"
LOG_FILTER='resource.type="cloud_run_revision" AND jsonPayload.service="financial-agent-event-collector"'
if gcloud logging sinks describe "${SINK_NAME}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "[기존 Sink 사용] ${SINK_NAME}"
else
  gcloud logging sinks create "${SINK_NAME}" "${DESTINATION}" \
    --project="${PROJECT_ID}" \
    --log-filter="${LOG_FILTER}"
fi

WRITER_ID="$(gcloud logging sinks describe "${SINK_NAME}" \
  --project="${PROJECT_ID}" --format='value(writerIdentity)')"
# bq add-iam-policy-binding은 일부 최신 CLI에서 allowlisting을 요구한다.
# 표준 GoogleSQL DCL은 데이터셋 수준에서 같은 권한을 부여한다.
bq query --use_legacy_sql=false --project_id="${PROJECT_ID}" \
  "GRANT \`roles/bigquery.dataEditor\`
   ON SCHEMA \`${PROJECT_ID}\`.${DATASET}
   TO \"${WRITER_ID}\";"

echo "[완료] 금융 행동 로그가 ${PROJECT_ID}:${DATASET}으로 전달됩니다."
