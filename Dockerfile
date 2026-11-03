# ---- stage 1: build the HMI (React) ----
FROM node:20-alpine AS hmi
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx tsc --noEmit && npx vite build --outDir /hmi

# ---- stage 2: API + served HMI ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=hmi /hmi ./app/static

RUN useradd --create-home pharmaflow && chown -R pharmaflow /app
USER pharmaflow

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
