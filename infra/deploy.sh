#!/usr/bin/env bash
# Build with Cloud Build and deploy to Cloud Run (idempotent). Usage: make deploy
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
read_cfg() { $PY -c "import yaml,sys;c=yaml.safe_load(open('config/cloud.yaml'));print(eval(sys.argv[1]))" "$1"; }
P=$(read_cfg 'c["project"]'); R=$(read_cfg 'c["region"]'); REPO=$(read_cfg 'c["artifact_repo"]')
SVC=$(read_cfg 'c["run_service"]'); SA="$(read_cfg 'c["service_account"]')@${P}.iam.gserviceaccount.com"
SECRET=$(read_cfg 'c["cloudsql"]["password_secret"]')
TAG=$(git rev-parse --short HEAD 2>/dev/null || date +%s)
IMG="${R}-docker.pkg.dev/${P}/${REPO}/app:${TAG}"

echo "==> building ${IMG}"
gcloud builds submit --project "$P" --region "$R" --tag "$IMG" .

echo "==> deploying ${SVC}"
gcloud run deploy "$SVC" --project "$P" --region "$R" --image "$IMG" \
  --service-account "$SA" --min-instances 0 --max-instances 2 --memory 1Gi --cpu 1 --timeout 120 \
  --allow-unauthenticated \
  --set-env-vars "GEMINI_MODE=${GEMINI_MODE:-live},DB_BACKEND=cloudsql,STORAGE_BACKEND=gcs,EVENTS_BACKEND=bigquery,SEARCH_BACKEND=vertex,GEMINI_CACHE_DIR=/app/cache/gemini" \
  --set-secrets "DB_PASSWORD=${SECRET}:latest"

URL=$(gcloud run services describe "$SVC" --project "$P" --region "$R" --format 'value(status.url)')
$PY infra/gcp.py record-run "$URL"
echo "==> deployed: $URL"
echo "    smoke test: make smoke URL=$URL"
