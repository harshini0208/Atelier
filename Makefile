PY      := .venv/bin/python
export PYTHONPATH := backend:.

.PHONY: setup dev api web test seed seed-cloud load-cloud demo-record gcp-setup gcp-status build deploy smoke

setup:            ## create venv, install backend + frontend deps
	python3.12 -m venv .venv
	.venv/bin/pip install -q -r backend/requirements-dev.txt
	cd frontend && npm install --no-audit --no-fund

seed:             ## generate catalog, SVG images, demo inspo, and load local SQLite + media folder
	$(PY) scripts/seed.py

dev:              ## run API (:8000) and Vite (:5173) together, offline (GEMINI_MODE=replay by default)
	@test -f local/wiw.db || $(MAKE) seed
	@trap 'kill 0' INT TERM; \
	GEMINI_MODE=$${GEMINI_MODE:-replay} $(PY) -m uvicorn wiw.main:app --reload --reload-dir backend --port 8000 & \
	cd frontend && npm run dev -- --host & \
	wait

api:
	GEMINI_MODE=$${GEMINI_MODE:-replay} $(PY) -m uvicorn wiw.main:app --reload --reload-dir backend --port 8000

test:             ## backend unit tests + frontend type check
	$(PY) -m pytest -q backend/tests
	cd frontend && npx tsc --noEmit -p .

load-cloud:       ## push seeded data to Cloud SQL, GCS, BigQuery and Vertex AI Search
	$(PY) scripts/load_cloud.py

demo-record:      ## run the scripted demo against live Gemini and fill cache/gemini/ for replay
	GEMINI_MODE=live $(PY) scripts/demo_record.py

gcp-setup:        ## idempotent: create missing wiw-* resources
	$(PY) infra/gcp.py setup

gcp-status:       ## found / missing, what we created, rough monthly cost
	$(PY) infra/gcp.py status

build:
	cd frontend && npm run build

deploy:           ## build image with Cloud Build and deploy to Cloud Run
	bash infra/deploy.sh

smoke:            ## smoke-test a running server: make smoke URL=https://...
	$(PY) scripts/smoke.py $${URL:-http://localhost:8000}
