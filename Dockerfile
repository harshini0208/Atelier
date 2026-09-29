# ---- build the React app
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---- API + static app on one Cloud Run service
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend:/app PORT=8080
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/wiw backend/wiw
COPY config config
COPY data data
COPY scripts/make_images.py scripts/make_images.py
COPY demo/inspo/generated demo/inspo/generated
COPY cache cache
COPY --from=web /web/dist frontend/dist
RUN useradd -m app && chown -R app /app/cache
USER app
CMD exec uvicorn wiw.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --proxy-headers
