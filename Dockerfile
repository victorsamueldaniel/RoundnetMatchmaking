# Web app image: builds the React client, then serves it with the FastAPI server.
FROM node:20-slim AS client
WORKDIR /build
COPY webapp/frontend/package.json webapp/frontend/package-lock.json ./
RUN npm ci
COPY webapp/frontend ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MPLBACKEND=Agg
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY core ./core
COPY ui ./ui
RUN pip install --no-cache-dir ".[web]"
COPY webapp/__init__.py ./webapp/__init__.py
COPY webapp/server ./webapp/server
COPY --from=client /build/dist ./webapp/frontend/dist
RUN useradd --create-home app
USER app
EXPOSE 8000
CMD ["sh", "-c", "uvicorn webapp.server.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
