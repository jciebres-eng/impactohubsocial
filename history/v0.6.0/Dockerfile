FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
ENV PORT=8080 IMPACTO_DB=/app/data/impacto.sqlite3 PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["python3","src/impacto/app.py"]
