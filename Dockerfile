# syntax=docker/dockerfile:1.7
# Imagem única: API + SPA compilada. O mesmo artefato roda como api, worker e job de migração (comandos diferentes).
# NÃO testada neste ambiente de build (sem daemon Docker) — validar no CI (job docker) antes do primeiro deploy.

FROM node:22-bookworm-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npx tsc -p tsconfig.json --noEmit && node build.mjs

FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 IMPACTO_ENV=production PORT=8080 \
    WEB_DIST_DIR=/app/web/dist STORAGE_LOCAL_DIR=/data/storage
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 postgresql-client tesseract-ocr tesseract-ocr-por ca-certificates \
    && rm -rf /var/lib/apt/lists/* && useradd --create-home --uid 10001 impacto && mkdir -p /data && chown impacto /data
WORKDIR /app
COPY backend/requirements.txt backend/requirements-optional.txt backend/
RUN pip install -r backend/requirements.txt -r backend/requirements-optional.txt
COPY VERSION ./
COPY config/ config/
COPY docs/legal/ docs/legal/
COPY infra/db/ infra/db/
COPY backend/impacto/ backend/impacto/
COPY backend/migrations/ backend/migrations/
COPY backend/start_container.sh /app/start_container.sh
COPY --from=web /web/dist web/dist
USER impacto
WORKDIR /app/backend
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD python3 -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8080\")}/healthz',timeout=4)"
# Entrypoint com etapas nomeadas (migrações → troca para impacto_app → ASGI). IMPACTO_ENV continua
# production: demonstração é decisão de quem sobe o contêiner (IMPACTO_ENV=development), nunca da
# imagem — a imagem recebida de fora fixava development, seed e um domínio de terceiro aqui.
CMD ["sh", "/app/start_container.sh"]
